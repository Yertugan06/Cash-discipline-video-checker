#!/usr/bin/env python3
"""Offline A13 OWLv2 comparison. Writes numeric/text JSON only, never frame artifacts.

Run the argv in gpu-command.json outside the Codex sandbox. All variants share one
checkpoint, prompt set, threshold, precision and 640-pixel model input. The runtime
baseline is LocalModels.objects on full frame plus its automatically calibrated desk.
Native tiles cover every camera position without consulting labels or detections.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from backend.f1.calibration import calibrate  # noqa: E402
from backend.f1.object_refinement import SourceCrop, native_tiles, remap_detections  # noqa: E402
from backend.f1.perception import LocalModels, load_perception_config, verify_weights  # noqa: E402
from backend.f1.vision_types import Detection  # noqa: E402

CLASSES = {
    "cash": {"cash", "bundle"},
    "id_card": {"id_card"},
    "bag": {"bag"},
    "food_cup": {"food", "cup"},
    "coat_bag": {"coat", "handbag"},
}
VARIANTS = ("full", "full_desk", "native_tiles", "full_desk_tiles")


def read_cases(source: Path) -> list[dict]:
    """Read only the literal FRAMES list; do not execute the old downloading probe."""
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FRAMES" for target in node.targets
        ):
            rows = ast.literal_eval(node.value)
            return [
                {"clip": clip, "t": t, "expected": expected} for clip, t, _note, expected in rows
            ]
    raise ValueError("No literal A13 FRAMES list was found")


def find_video(videos: Path, clip: str) -> Path:
    """Names select an evaluation input only; they are never passed to inference."""
    number = int(clip.split("-")[-1])
    matches = []
    for path in videos.rglob("*"):
        if path.suffix.lower() not in {".mov", ".mp4"}:
            continue
        match = re.fullmatch(r"[XХ]-0*(\d+)", path.stem)
        if match and int(match[1]) == number:
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"Expected one input video for {clip}; found {len(matches)}")
    return matches[0]


def grab_frame(path: Path, timestamp: float):
    """Decode directly from the native video. No disk images, resizing or cloud I/O."""
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("Video decoder could not open input")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or count <= 0 or not 0 <= timestamp < count / fps:
            raise ValueError("Requested timestamp is outside the recording or duration is unknown")
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = cap.read()
        if not ok:
            raise ValueError("Video decoder could not read the requested frame")
        metadata = {
            "requested_t": timestamp,
            "decoded_t": float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000,
            "frame_index_after_read": int(cap.get(cv2.CAP_PROP_POS_FRAMES)),
            "fps": fps,
            "duration_sec": count / fps,
            "source_size_wh": [int(frame.shape[1]), int(frame.shape[0])],
        }
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), metadata
    finally:
        cap.release()


class OwlProbe(LocalModels):
    """Load only OWLv2 while inheriting the unchanged production objects/context/nms."""

    def __init__(self, weights: Path, device: str, threads: int, config: dict):
        import torch
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        torch.set_num_threads(threads)
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; run gpu-command.json outside the sandbox")
        self.torch, self.device, self.config = torch, device, config
        self.text_inputs = {}
        self.owl_processor = Owlv2Processor.from_pretrained(
            weights / "objects", local_files_only=True
        )
        self.owl_model = (
            Owlv2ForObjectDetection.from_pretrained(
                weights / "objects", local_files_only=True, use_safetensors=True
            )
            .eval()
            .to(device)
        )
        self.last_input_shape: list[int] = []
        self.last_invalid_output_values = 0

        def record_shape(_module, _args, kwargs):
            self.last_input_shape = list(kwargs["pixel_values"].shape)

        def record_invalid_outputs(_module, _args, output):
            self.last_invalid_output_values = sum(
                int((~torch.isfinite(value)).sum().item())
                for value in (output.logits, output.pred_boxes)
            )

        self.owl_model.register_forward_pre_hook(record_shape, with_kwargs=True)
        self.owl_model.register_forward_hook(record_invalid_outputs)

    def sync(self) -> None:
        if self.device == "cuda":
            self.torch.cuda.synchronize()


def run_crop(models: OwlProbe, image, crop: SourceCrop, prompts: dict, name: str) -> dict[str, Any]:
    crop.validate(image.width, image.height)
    started = time.perf_counter()
    models.last_invalid_output_values = 0
    try:
        detections = models.objects(image.crop(crop.bounds), prompts)
        models.sync()
        if models.last_invalid_output_values:
            raise ValueError("OWLv2 emitted non-finite logits or boxes")
        mapped = remap_detections(detections, crop, image.width, image.height)
        return {
            "name": name,
            "crop_xyxy_px": list(crop.bounds),
            "source_crop_size_wh": list(crop.size),
            "model_input_shape": models.last_input_shape,
            "sec": time.perf_counter() - started,
            "ok": True,
            "invalid_output_values": 0,
            "detections": [d.model_dump() for d in mapped],
        }
    except Exception as exc:
        # A diagnostic must preserve failed crops as unknown, never as negative evidence.
        return {
            "name": name,
            "crop_xyxy_px": list(crop.bounds),
            "source_crop_size_wh": list(crop.size),
            "sec": time.perf_counter() - started,
            "ok": False,
            "invalid_output_values": models.last_invalid_output_values,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "detections": [],
        }


def union_prediction(crops: list[dict]) -> dict:
    """A positive anywhere scores the full frame. Incomplete empty unions are unknown."""
    detections = [Detection.model_validate(d) for crop in crops for d in crop["detections"]]
    detections = LocalModels.nms(detections)
    complete = bool(crops) and all(crop["ok"] for crop in crops)
    present = {d.label for d in detections}
    return {
        "pred": {
            key: True if present & labels else False if complete else None
            for key, labels in CLASSES.items()
        },
        "ok": complete,
        "failed_crops": sum(not crop["ok"] for crop in crops),
        "invalid_output_values": sum(c.get("invalid_output_values", 0) for c in crops),
        "crop_names": [crop["name"] for crop in crops],
        "sec": sum(crop["sec"] for crop in crops),
        "detections": [d.model_dump() for d in detections],
    }


def summarise(records: list[dict]) -> dict:
    summary = {}
    for variant in VARIANTS:
        per_class = {}
        for key in CLASSES:
            counts = dict.fromkeys(
                (
                    "tp",
                    "fp",
                    "fn",
                    "tn",
                    "unknown",
                    "unknown_positive",
                    "unknown_negative",
                    "unlabelled",
                ),
                0,
            )
            for record in records:
                truth = record["expected"].get(key)
                if type(truth) is not bool:
                    counts["unlabelled"] += 1
                    continue
                prediction = record["variants"][variant]["pred"].get(key)
                if prediction is None:
                    counts["unknown"] += 1
                    counts["unknown_positive" if truth else "unknown_negative"] += 1
                elif type(prediction) is not bool:
                    raise ValueError("Presence predictions must be bool or None")
                else:
                    counts[
                        ("tp" if prediction else "fn") if truth else ("fp" if prediction else "tn")
                    ] += 1
            per_class[key] = counts
        times = [r["variants"][variant]["sec"] for r in records]
        summary[variant] = {
            "classes": per_class,
            "inference_sec_total": sum(times),
            "inference_sec_mean": sum(times) / len(times) if times else None,
            "failed_crops": sum(r["variants"][variant]["failed_crops"] for r in records),
            "invalid_output_values": sum(
                r["variants"][variant]["invalid_output_values"] for r in records
            ),
        }
    return summary


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument(
        "--weights", type=Path, required=True, help="Existing complete runtime weights"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--tile-size", type=int, default=640)
    parser.add_argument("--tile-overlap", type=float, default=0.25)
    parser.add_argument(
        "--preflight", action="store_true", help="CPU input/weight checks; no inference"
    )
    args = parser.parse_args(argv)
    if args.threads <= 0:
        parser.error("--threads must be positive")
    # Validate tile parameters even when a model cannot be loaded.
    native_tiles(1, 1, tile_size=args.tile_size, overlap=args.tile_overlap)
    source = ROOT / "attempts/A13-detection-spike/scripts/spike_test.py"
    cases = read_cases(source)
    config = load_perception_config(ROOT / "config/perception.yaml")
    manifest_hash = verify_weights(args.weights)
    manifest = json.loads((args.weights / "manifest.json").read_text(encoding="utf-8"))
    objects_manifest = next(m for m in manifest["models"] if m["name"] == "objects")
    metadata = {
        "status": "preflight" if args.preflight else "running",
        "argv": sys.argv[1:] if argv is None else argv,
        "model": objects_manifest,
        "manifest_sha256": manifest_hash,
        "label_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "perception_sha256": hashlib.sha256(
            (ROOT / "backend/f1/perception.py").read_bytes()
        ).hexdigest(),
        "labels": dict(Counter(k for c in cases for k in c["expected"] if k in CLASSES)),
        "object_prompts": config["object_prompts"],
        "object_score": config["object_score"],
        "owl_image_size": config["owl_image_size"],
        "device": args.device,
        "precision": "cuda autocast float16" if args.device == "cuda" else "float32",
        "tile_size": args.tile_size,
        "tile_overlap": args.tile_overlap,
        "limitations": [
            "Frame-presence gold only: no box accuracy or per-crop labels.",
            "Cash means cash/bundle detected anywhere; no desk position or owner is inferred.",
            "Negative ID frames cannot establish interval-level non-presentation.",
            "No rule decisions or organizer reason/timing validation.",
            "safe_open and screen are state labels and excluded from object scoring.",
            "Full/desk detections are reused across variants; times are summed component costs.",
            "First forward includes warmup; calibration time reported separately.",
        ],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "metadata.json", metadata)
    if args.preflight:
        inputs = []
        for case in cases:
            image, frame_metadata = grab_frame(find_video(args.videos, case["clip"]), case["t"])
            tiles = native_tiles(*image.size, tile_size=args.tile_size, overlap=args.tile_overlap)
            inputs.append({**case, **frame_metadata, "tiles_xyxy_px": [c.bounds for c in tiles]})
        write_json(args.out / "preflight.json", inputs)
        print(
            json.dumps(
                {
                    "status": "preflight_ok",
                    "cases": len(cases),
                    "labels": metadata["labels"],
                    "out": str(args.out),
                }
            ),
            flush=True,
        )
        return 0

    started = time.perf_counter()
    try:
        models = OwlProbe(args.weights, args.device, args.threads, config)
    except Exception as exc:
        failure = {
            "status": "model_unavailable",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_json(args.out / "metadata.json", {**metadata, **failure})
        records = [{**c, "variants": {v: union_prediction([]) for v in VARIANTS}} for c in cases]
        write_json(args.out / "results.json", records)
        write_json(args.out / "summary.json", summarise(records))
        print(json.dumps(failure), flush=True)
        return 2
    metadata["load_sec"] = time.perf_counter() - started
    import torch
    import transformers

    metadata.update(
        {
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "processor_size": models.owl_processor.image_processor.size,
            "processor_do_pad": models.owl_processor.image_processor.do_pad,
        }
    )
    records = []
    has_errors = False
    for case in cases:
        record = dict(case)
        try:
            path = find_video(args.videos, case["clip"])
            image, frame_metadata = grab_frame(path, case["t"])
            record.update(frame_metadata)
            width, height = image.size
            full = SourceCrop(0, 0, width, height)
            # Same 2 fps calibration indices as perceive_video, with no clip overrides.
            calibration_times = sorted(
                {0.0, 1.0, max(0.0, round(config["calibration_sec"] * 2) - 1) / 2}
            )
            calibration_calls = []
            for t in calibration_times:
                scene_image, _ = grab_frame(path, t)
                calibration_calls.append(
                    run_crop(models, scene_image, full, config["scene_prompts"], f"calibration_{t}")
                )
            candidates = [
                Detection.model_validate(d) for c in calibration_calls for d in c["detections"]
            ]
            scene = calibrate(candidates, ROOT / "config/overrides.yaml", "diagnostic_no_override")
            record["calibration"] = {
                "calls": calibration_calls,
                "scene": scene.model_dump(),
                "sec": sum(c["sec"] for c in calibration_calls),
            }
            full_call = run_crop(models, image, full, config["object_prompts"], "full")
            desk_calls = []
            if "desk" in scene.objects:
                x1, y1, x2, y2 = scene.objects["desk"].box
                desk = SourceCrop(
                    max(0, int(x1 * width) - 4),
                    max(0, int(y1 * height) - 4),
                    min(width, int(x2 * width) + 4),
                    min(height, int(y2 * height) + 4),
                )
                if min(desk.size) >= 32:
                    desk_calls.append(
                        run_crop(models, image, desk, config["object_prompts"], "desk")
                    )
            if any(not c["ok"] for c in calibration_calls):
                desk_calls.append(
                    {"name": "desk_calibration_failed", "ok": False, "detections": [], "sec": 0.0}
                )
            tiles = native_tiles(width, height, tile_size=args.tile_size, overlap=args.tile_overlap)
            tile_calls = [
                run_crop(models, image, crop, config["object_prompts"], f"tile_{i}")
                for i, crop in enumerate(tiles)
            ]
            record["calls"] = [full_call, *desk_calls, *tile_calls]
            record["variants"] = {
                "full": union_prediction([full_call]),
                "full_desk": union_prediction([full_call, *desk_calls]),
                "native_tiles": union_prediction(tile_calls),
                "full_desk_tiles": union_prediction([full_call, *desk_calls, *tile_calls]),
            }
        except Exception as exc:
            record["error_type"], record["error"] = type(exc).__name__, str(exc)
            record["variants"] = {v: union_prediction([]) for v in VARIANTS}
        records.append(record)
        has_errors |= "error" in record or any(not v["ok"] for v in record["variants"].values())
        write_json(args.out / "results.json", records)
        write_json(args.out / "summary.json", summarise(records))
        print(
            json.dumps(
                {
                    "clip": case["clip"],
                    "t": case["t"],
                    "pred": {v: r["pred"] for v, r in record["variants"].items()},
                    "error": record.get("error"),
                }
            ),
            flush=True,
        )
    metadata.update(
        {
            "status": "complete_with_errors" if has_errors else "complete",
            "wall_sec": time.perf_counter() - started,
            "cases": len(records),
        }
    )
    write_json(args.out / "metadata.json", metadata)
    print(json.dumps({"status": metadata["status"], "out": str(args.out)}), flush=True)
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
