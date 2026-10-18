"""Local-only RT-DETR, OWLv2, OpenCLIP and RTMPose inference; no rule decisions."""

import hashlib
import json
import os
import time
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from backend.config import ROOT, Settings
from backend.f1.calibration import calibrate
from backend.f1.vision_types import Box, Detection, Observation, Scene, State, overlap

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/forte-matplotlib")


def load_perception_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {
        "calibration_sec",
        "object_interval_sec",
        "state_interval_sec",
        "hysteresis_sec",
        "exit_gap_sec",
        "hand_distance",
        "glass_margin",
        "object_score",
        "person_score",
        "person_min_height",
        "state_score",
        "state_margin",
        "owl_image_size",
        "person_image_size",
        "scene_prompts",
        "object_prompts",
        "state_prompts",
        "version",
    }
    if not isinstance(config, dict) or set(config) - {"desk_objects"} != required:
        raise ValueError("Invalid perception configuration keys")
    if not isinstance(config.setdefault("desk_objects", False), bool):
        raise ValueError("Invalid perception setting: desk_objects")
    for key in required - {"scene_prompts", "object_prompts", "state_prompts"}:
        if (
            not isinstance(config[key], (int, float))
            or not np.isfinite(config[key])
            or config[key] <= 0
        ):
            raise ValueError(f"Invalid perception setting: {key}")
    for key in (
        "object_score",
        "person_score",
        "person_min_height",
        "state_score",
        "state_margin",
        "hand_distance",
        "glass_margin",
    ):
        if config[key] >= 1:
            raise ValueError(f"{key} must be below 1")
    if int(config["owl_image_size"]) % 16:
        raise ValueError("owl_image_size must be a multiple of 16")
    return config


def verify_weights(weights_dir: Path) -> str:
    expected = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    installed_path = weights_dir / "manifest.json"
    if not installed_path.is_file():
        raise ValueError(
            "Model weights are missing. Run scripts/download_weights.sh before analysis."
        )
    installed = json.loads(installed_path.read_text(encoding="utf-8"))
    if installed.get("models") != expected["models"]:
        raise ValueError("Model manifest does not match models.lock.json; download weights again")
    for model in expected["models"]:
        for artifact in model["files"]:
            path = weights_dir / model["name"] / artifact["path"]
            if not path.is_file() or path.stat().st_size != artifact["size"]:
                raise ValueError(
                    f"Missing or truncated model file: {model['name']}/{artifact['path']}"
                )
    return hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()


def normal_box(box, width: int, height: int) -> Box | None:
    values = np.asarray(box, dtype=np.float64) / [width, height, width, height]
    if not np.isfinite(values).all():
        return None
    x1, y1, x2, y2 = np.clip(values, 0, 1).tolist()
    return (x1, y1, x2, y2) if x2 - x1 > 0.005 and y2 - y1 > 0.005 else None


class LocalModels:
    def __init__(self, weights_dir: Path, device: str, threads: int, config: dict):
        import onnxruntime as ort

        ort.disable_telemetry_events()
        import torch
        from transformers import (
            CLIPModel,
            CLIPProcessor,
            Owlv2ForObjectDetection,
            Owlv2Processor,
            RTDetrForObjectDetection,
            RTDetrImageProcessor,
        )

        verify_weights(weights_dir)
        torch.set_num_threads(threads)
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError(
                "DEVICE=cuda requested but CUDA is unavailable; install the NVIDIA build"
            )
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() and device != "cpu" else "cpu"
        self.config = config
        self.person_processor = RTDetrImageProcessor.from_pretrained(
            weights_dir / "person", local_files_only=True
        )
        self.person_model = (
            RTDetrForObjectDetection.from_pretrained(
                weights_dir / "person",
                local_files_only=True,
                use_safetensors=True,
            )
            .eval()
            .to(self.device)
        )
        self.owl_processor = Owlv2Processor.from_pretrained(
            weights_dir / "objects", local_files_only=True
        )
        self.owl_model = (
            Owlv2ForObjectDetection.from_pretrained(
                weights_dir / "objects",
                local_files_only=True,
                use_safetensors=True,
            )
            .eval()
            .to(self.device)
        )
        self.clip_processor = CLIPProcessor.from_pretrained(
            weights_dir / "states", local_files_only=True
        )
        self.clip_model = (
            CLIPModel.from_pretrained(
                weights_dir / "states",
                local_files_only=True,
                use_safetensors=True,
            )
            .eval()
            .to(self.device)
        )
        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.pose_device = (
            "cuda"
            if self.device == "cuda" and "CUDAExecutionProvider" in ort.get_available_providers()
            else "cpu"
        )
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if self.pose_device == "cuda"
            else ["CPUExecutionProvider"]
        )
        self.pose_model = ort.InferenceSession(
            str(weights_dir / "pose/rtmpose-m-wholebody.onnx"),
            options,
            providers=providers,
        )
        self.text_inputs = {}
        self.state_embeddings = {}

    def context(self):
        return (
            self.torch.autocast("cuda", dtype=self.torch.float16)
            if self.device == "cuda"
            else nullcontext()
        )

    def people(self, image) -> list[Detection]:
        torch = self.torch
        size = int(self.config["person_image_size"])
        inputs = self.person_processor(
            images=image, size={"height": size, "width": size}, return_tensors="pt"
        ).to(self.device)
        with torch.inference_mode(), self.context():
            result = self.person_model(**inputs)
        result = self.person_processor.post_process_object_detection(
            result,
            target_sizes=[(image.height, image.width)],
            threshold=self.config["person_score"],
        )[0]
        detections = []
        for box, score, label in zip(
            result["boxes"], result["scores"], result["labels"], strict=True
        ):
            if int(label) != 0:
                continue
            normal = normal_box(box.detach().cpu().numpy(), image.width, image.height)
            # A box shorter than this is not a person in this room (e.g. a blob on the laptop)
            # but would still win the cashier role by sitting closest to the laptop.
            if normal and normal[3] - normal[1] >= self.config["person_min_height"]:
                detections.append(Detection(label="person", score=float(score), box=normal))
        return self.nms(detections)

    @staticmethod
    def nms(detections: list[Detection]) -> list[Detection]:
        selected = []
        for item in sorted(detections, key=lambda d: d.score, reverse=True):
            if not any(
                (d.label == item.label and overlap(item.box, d.box) > 0.4)
                or ({d.label, item.label} <= {"cash", "bundle"} and overlap(item.box, d.box) > 0.6)
                for d in selected
            ):
                selected.append(item)
        return selected

    def objects(self, image, prompt_groups: dict[str, list[str]]) -> list[Detection]:
        torch = self.torch
        labels = [label for label, prompts in prompt_groups.items() for _ in prompts]
        prompts = [prompt for values in prompt_groups.values() for prompt in values]
        key = tuple(prompts)
        if key not in self.text_inputs:
            self.text_inputs[key] = self.owl_processor.tokenizer(
                prompts, padding="max_length", truncation=True, return_tensors="pt"
            ).to(self.device)
        size = int(self.config["owl_image_size"])
        pixels = self.owl_processor.image_processor(
            images=image, size={"height": size, "width": size}, return_tensors="pt"
        ).to(self.device)
        with torch.inference_mode(), self.context():
            output = self.owl_model(
                **pixels, **self.text_inputs[key], interpolate_pos_encoding=True
            )
        result = self.owl_processor.post_process_grounded_object_detection(
            output,
            threshold=self.config["object_score"],
            target_sizes=[(image.height, image.width)],
        )[0]
        detections = []
        for box, score, label in zip(
            result["boxes"], result["scores"], result["labels"], strict=True
        ):
            normal = normal_box(box.detach().cpu().numpy(), image.width, image.height)
            if normal:
                detections.append(
                    Detection(label=labels[int(label)], score=float(score), box=normal)
                )
        return self.nms(detections)

    def state(self, image, family: str) -> State:
        torch = self.torch
        groups = self.config["state_prompts"][family]
        names = list(groups)
        if family not in self.state_embeddings:
            inputs = self.clip_processor(
                text=[prompt for values in groups.values() for prompt in values],
                padding=True,
                return_tensors="pt",
            ).to(self.device)
            with torch.inference_mode(), self.context():
                features = self.clip_model.get_text_features(**inputs)
                features = features / features.norm(dim=-1, keepdim=True)
                prototypes = []
                offset = 0
                for prompts in groups.values():
                    prototypes.append(features[offset : offset + len(prompts)].mean(dim=0))
                    offset += len(prompts)
                features = torch.stack(prototypes)
                self.state_embeddings[family] = features / features.norm(dim=-1, keepdim=True)
        inputs = self.clip_processor.image_processor(
            images=image,
            size={"height": 224, "width": 224},
            do_center_crop=False,
            return_tensors="pt",
        ).to(self.device)
        with torch.inference_mode(), self.context():
            features = self.clip_model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
            scores = (
                self.clip_model.logit_scale.exp() * features @ self.state_embeddings[family].T
            ).softmax(dim=-1)[0]
        values, indices = scores.float().cpu().topk(2)
        score, margin = float(values[0]), float(values[0] - values[1])
        state = names[int(indices[0])]
        if score < self.config["state_score"] or margin < self.config["state_margin"]:
            state = "unknown"
        return State(value=state, score=score, margin=margin)

    def pose(self, image, person: Detection) -> None:
        import cv2

        height, width = image.shape[:2]
        _, _, input_height, input_width = self.pose_model.get_inputs()[0].shape
        x1, y1, x2, y2 = np.asarray(person.box) * [width, height, width, height]
        midpoint = np.array([(x1 + x2) / 2, (y1 + y2) / 2], dtype=np.float32)
        scale = np.array([x2 - x1, y2 - y1], dtype=np.float32) * 1.25
        aspect = input_width / input_height
        if scale[0] > scale[1] * aspect:
            scale[1] = scale[0] / aspect
        else:
            scale[0] = scale[1] * aspect
        source = np.float32(
            [midpoint - scale / 2, midpoint + [-scale[0] / 2, scale[1] / 2], midpoint + scale / 2]
        )
        target = np.float32([[0, 0], [0, input_height], [input_width, input_height]])
        matrix = cv2.getAffineTransform(source, target)
        crop = cv2.warpAffine(image, matrix, (input_width, input_height))
        crop = (
            crop.astype(np.float32) - np.array([123.675, 116.28, 103.53], np.float32)
        ) / np.array([58.395, 57.12, 57.375], np.float32)
        tensor = np.transpose(crop, (2, 0, 1))[None].astype(np.float32)
        simcc_x, simcc_y = self.pose_model.run(None, {self.pose_model.get_inputs()[0].name: tensor})
        x, y = simcc_x[0].argmax(axis=-1) / 2, simcc_y[0].argmax(axis=-1) / 2
        confidence = np.minimum(simcc_x[0].max(axis=-1), simcc_y[0].max(axis=-1))
        points = np.stack([x, y, np.ones_like(x)], axis=-1) @ cv2.invertAffineTransform(matrix).T
        if not np.isfinite(points).all() or not np.isfinite(confidence).all():
            raise ValueError("RTMPose produced non-finite keypoints")
        points = points / [width, height]
        decoded = [
            (float(p[0]), float(p[1]), float(s)) for p, s in zip(points, confidence, strict=True)
        ]
        person.body = decoded[:17]
        person.hands = decoded[91:133] if len(decoded) >= 133 else []


@lru_cache(maxsize=1)
def get_models(weights_dir: Path, device: str, threads: int, config_text: str) -> LocalModels:
    return LocalModels(weights_dir, device, threads, json.loads(config_text))


def crop_image(image, box: Box, margin: float = 0.10):
    width, height = image.size
    x1, y1, x2, y2 = box
    padding_x, padding_y = (x2 - x1) * margin, (y2 - y1) * margin
    left, top = max(0, x1 - padding_x), max(0, y1 - padding_y)
    right, bottom = min(1, x2 + padding_x), min(1, y2 + padding_y)
    return image.crop(
        (
            int(left * width),
            int(top * height),
            max(int(right * width), int(left * width) + 1),
            max(int(bottom * height), int(top * height) + 1),
        )
    )


def perceive_video(
    frames: list[Path], checksum: str, settings: Settings, deadline: float, fps: float
) -> tuple[Scene, list[Observation], dict]:
    import supervision as sv
    from PIL import Image

    config = load_perception_config(settings.perception_config)
    weights_hash = verify_weights(settings.weights_dir)
    overrides_text = settings.overrides_path.read_text(encoding="utf-8")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "implementation": hashlib.sha256(
                    b"".join(
                        (ROOT / "backend" / "f1" / name).read_bytes()
                        for name in ("perception.py", "calibration.py", "vision_types.py")
                    )
                ).hexdigest(),
                "models": weights_hash,
                "config": config,
                "overrides": overrides_text,
                "fps": fps,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    cache = settings.cache_dir / checksum / f"{fingerprint}.json"
    if cache.is_file() and settings.reuse_perception:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        return (
            Scene.model_validate(payload["scene"]),
            [Observation.model_validate(v) for v in payload["observations"]],
            {**config, "cache_hit": True},
        )
    models = get_models(
        settings.weights_dir,
        settings.device,
        settings.cpu_threads,
        json.dumps(config, sort_keys=True),
    )
    calibration_indices = sorted(
        {
            0,
            min(len(frames) - 1, round(fps)),
            max(0, min(len(frames) - 1, round(config["calibration_sec"] * fps) - 1)),
        }
    )
    candidates = []
    for index in calibration_indices:
        if time.monotonic() > deadline:
            raise TimeoutError("Perception exceeded processing time limit during calibration")
        with Image.open(frames[index]) as image:
            candidates.extend(models.objects(image.convert("RGB"), config["scene_prompts"]))
    scene = calibrate(candidates, settings.overrides_path, checksum)
    trackers = {
        label: sv.ByteTrack(
            track_activation_threshold=max(0.01, config["object_score"] - 0.1),
            lost_track_buffer=30,
            frame_rate=max(1, round(fps)),
            minimum_consecutive_frames=1,
        )
        for label in ["person", *config["object_prompts"]]
    }
    observations = []
    last_objects = []
    last_states = {}
    last_object_time = last_state_time = -100.0
    for index, frame in enumerate(frames):
        if time.monotonic() > deadline:
            raise TimeoutError("Perception exceeded the configured processing time limit")
        timestamp = index / fps
        with Image.open(frame) as raw:
            image = raw.convert("RGB")
        people = models.people(image)
        if timestamp - last_object_time + 1e-6 >= config["object_interval_sec"]:
            last_objects = models.objects(image, config["object_prompts"])
            if "desk" in scene.objects:
                x1, y1, x2, y2 = scene.objects["desk"].box
                left, top = max(0, int(x1 * image.width) - 4), max(0, int(y1 * image.height) - 4)
                right, bottom = (
                    min(image.width, int(x2 * image.width) + 4),
                    min(image.height, int(y2 * image.height) + 4),
                )
                if right - left >= 32 and bottom - top >= 32:
                    desk_crop = image.crop((left, top, right, bottom))
                    small = config["object_prompts"]
                    for item in models.objects(desk_crop, small):
                        a, b, c, d = item.box
                        item.box = (
                            (left + a * (right - left)) / image.width,
                            (top + b * (bottom - top)) / image.height,
                            (left + c * (right - left)) / image.width,
                            (top + d * (bottom - top)) / image.height,
                        )
                        last_objects.append(item)
                    last_objects = models.nms(last_objects)
            last_object_time = timestamp
        current = people + [item.model_copy(deep=True) for item in last_objects]
        tracked = []
        for label, tracker in trackers.items():
            matches = [d for d in current if d.label == label]
            values = sv.Detections(
                xyxy=np.array([d.box for d in matches], dtype=np.float32).reshape(-1, 4),
                confidence=np.array([d.score for d in matches], dtype=np.float32),
                class_id=np.zeros(len(matches), dtype=int),
            )
            result = tracker.update_with_detections(values)
            for box, score, identity in zip(
                result.xyxy, result.confidence, result.tracker_id, strict=True
            ):
                tracked.append(
                    Detection(
                        label=label,
                        score=float(score),
                        box=tuple(box.tolist()),
                        track_id=f"{label}:{int(identity)}",
                    )
                )
        pixels = np.asarray(image)
        for person in (d for d in tracked if d.label == "person"):
            models.pose(pixels, person)
        if timestamp - last_state_time + 1e-6 >= config["state_interval_sec"]:
            last_states = {
                name: models.state(crop_image(image, detection.box), name)
                for name, detection in scene.objects.items()
                if name in config["state_prompts"]
            }
            for person in (d for d in tracked if d.label == "person"):
                last_states[person.track_id] = models.state(crop_image(image, person.box), "person")
            for bag in (d for d in tracked if d.label == "bag"):
                last_states[bag.track_id] = models.state(crop_image(image, bag.box), "bag")
            last_state_time = timestamp
        observations.append(
            Observation(timestamp_sec=timestamp, detections=tracked, states=last_states.copy())
        )
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".partial")
    temporary.write_text(
        json.dumps(
            {"scene": scene.model_dump(), "observations": [o.model_dump() for o in observations]}
        ),
        encoding="utf-8",
    )
    temporary.replace(cache)
    return scene, observations, {**config, "cache_hit": False}
