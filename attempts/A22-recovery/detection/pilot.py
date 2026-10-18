"""Approved-VM-only offline two-variant pilot. Outputs numbers/boxes, never image files."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ("base", "weights", "videos", "cache", "manifest", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.base))
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    from backend.f1.detection_refinement import Proposal, native_proposals, presence, refine
    from backend.f1.object_refinement import SourceCrop
    from backend.f1.perception import LocalModels, load_perception_config
    from backend.f1.vision_types import Observation, Scene

    cases = json.loads(args.manifest.read_text())
    if len(cases) != 20:
        raise ValueError("Pilot requires all twenty fixed development cases")
    config = load_perception_config(args.base / "config/perception.yaml")
    config["owl_image_size"] = 640
    config["object_score"] = 0.12
    weights_manifest = json.loads((args.weights / "manifest.json").read_text())
    objects = [m for m in weights_manifest["models"] if m.get("name") == "objects"]
    if len(objects) != 1 or (objects[0]["repo"], objects[0]["revision"]) != (
        "google/owlv2-base-patch16-ensemble",
        "cfd3195ba4ea9592eec887ded089f4c08eff231d",
    ):
        raise ValueError("Expected the pinned baseline OWLv2 object checkpoint")
    args.out.mkdir(parents=True, exist_ok=False)
    registration = {
        "base_commit": "5fae84bc10415111a04b5982d156727ca80f788a",
        "model": "google/owlv2-base-patch16-ensemble",
        "model_input": 640,
        "threshold": 0.12,
        "prompts": config["object_prompts"],
        "variants": ["full_desk", "full_desk_plus_native128"],
        "roi_cap": 12,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "weights_metadata": objects[0],
        "development_only": True,
    }
    (args.out / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    lock_path = Path.home() / ".cache/datathon-workers/gpu.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        import cv2
        import torch
        from PIL import Image
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        if not torch.cuda.is_available():
            raise RuntimeError("GPU unavailable: this pilot must be run by the orchestrator")

        class OwlOnly(LocalModels):
            def __init__(self):
                self.torch, self.device, self.config = torch, "cuda", config
                self.owl_processor = Owlv2Processor.from_pretrained(
                    args.weights / "objects", local_files_only=True
                )
                self.owl_model = (
                    Owlv2ForObjectDetection.from_pretrained(
                        args.weights / "objects", local_files_only=True
                    )
                    .eval()
                    .to("cuda")
                )
                self.text_inputs = {}

        model_started = time.perf_counter()
        try:
            models = OwlOnly()
        except (OSError, ValueError, RuntimeError) as exc:
            (args.out / "startup-error.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "cases_inferred": 0,
                        "predictions": "unknown",
                    },
                    indent=2,
                )
                + "\n"
            )
            raise
        model_load_sec = time.perf_counter() - model_started
        records = []
        source = "google/owlv2-base-patch16-ensemble@cfd3195ba4ea9592eec887ded089f4c08eff231d"

        def detect(image, prompts):
            torch.cuda.synchronize()
            result = models.objects(image, prompts)
            torch.cuda.synchronize()
            return result

        videos = {}
        for path in args.videos.glob("*.mov"):
            match = re.search(r"(\d+)$", path.stem)
            if match:
                videos[int(match.group(1))] = path
        for case in cases:
            started = time.perf_counter()
            row = {
                "clip": case["clip"],
                "t": case["t"],
                "expected": case["expected"],
                "variants": {},
            }
            try:
                path = videos[int(case["clip"].split("-")[-1])]
                with path.open("rb") as stream:
                    checksum = hashlib.file_digest(stream, "sha256").hexdigest()
                payloads = list((args.cache / checksum).glob("*.json"))
                if len(payloads) != 1:
                    raise ValueError("Expected exactly one pinned numeric cache")
                payload = json.loads(payloads[0].read_text())
                scene = Scene.model_validate(payload["scene"])
                observation = min(
                    (Observation.model_validate(o) for o in payload["observations"]),
                    key=lambda o: abs(o.timestamp_sec - case["t"]),
                )
                if abs(observation.timestamp_sec - case["t"]) > 0.5:
                    raise ValueError("No temporally local numeric observation")
                cap = cv2.VideoCapture(str(path))
                try:
                    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                    if not 0 <= case["t"] < duration:
                        raise ValueError("Evaluation timestamp outside recording")
                    cap.set(cv2.CAP_PROP_POS_MSEC, case["t"] * 1000)
                    ok, pixels = cap.read()
                    if not ok:
                        raise OSError("Frame decode failed")
                    image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                finally:
                    cap.release()
                full = Proposal(SourceCrop(0, 0, image.width, image.height), "full")
                baseline = [full]
                desk = scene.objects.get("desk")
                if desk is not None:
                    a, b, c, d = desk.box
                    crop = SourceCrop(
                        max(0, int(a * image.width) - 4),
                        max(0, int(b * image.height) - 4),
                        min(image.width, int(c * image.width) + 4),
                        min(image.height, int(d * image.height) + 4),
                    )
                    crop.validate(image.width, image.height)
                    if min(crop.size) >= 32:
                        baseline.append(Proposal(crop, "desk"))
                base_d, base_p = refine(
                    image, baseline, detect, config["object_prompts"], model_source=source
                )
                proposals = native_proposals(image.width, image.height, scene, observation)
                extra_d, extra_p = refine(
                    image, proposals, detect, config["object_prompts"], model_source=source
                )
                for variant, detections, provenance in (
                    ("full_desk", base_d, base_p),
                    (
                        "full_desk_plus_native128",
                        LocalModels.nms(base_d + extra_d),
                        base_p + extra_p,
                    ),
                ):
                    row["variants"][variant] = {
                        "pred": presence(detections, provenance),
                        "detections": [d.model_dump() for d in detections],
                        "calls": provenance,
                        "inference_sec": sum(p["sec"] for p in provenance),
                    }
                row.update(
                    sha256=checksum, no_proposal=not proposals, proposal_count=len(proposals)
                )
            except (OSError, ValueError, RuntimeError, KeyError, ZeroDivisionError) as exc:
                row["error"] = type(exc).__name__ + ": " + str(exc)
                for variant in registration["variants"]:
                    row["variants"][variant] = {
                        "pred": {"cash": None, "id_card": None},
                        "detections": [],
                        "calls": [],
                        "inference_sec": None,
                    }
            row["wall_sec"] = time.perf_counter() - started
            records.append(row)
            (args.out / "results.json").write_text(
                json.dumps(records, indent=2, allow_nan=False) + "\n"
            )
            print(
                json.dumps(
                    {
                        "done": len(records),
                        "clip": row["clip"],
                        "pred": {k: v["pred"] for k, v in row["variants"].items()},
                    }
                ),
                flush=True,
            )
        summary = {}
        for variant in registration["variants"]:
            summary[variant] = {}
            times = [
                r["variants"][variant]["inference_sec"]
                for r in records
                if r["variants"][variant]["inference_sec"] is not None
            ]
            summary[variant]["latency"] = {
                "measured_frames": len(times),
                "total_sec": sum(times),
                "median_sec": statistics.median(times) if times else None,
                "max_sec": max(times) if times else None,
            }
            for label in ("cash", "id_card"):
                counts = dict.fromkeys(
                    ("tp", "fp", "fn", "tn", "unknown_positive", "unknown_negative", "unlabelled"),
                    0,
                )
                for row in records:
                    truth, prediction = (
                        row["expected"].get(label),
                        row["variants"][variant]["pred"][label],
                    )
                    if type(truth) is not bool:
                        key = "unlabelled"
                    elif prediction is None:
                        key = "unknown_positive" if truth else "unknown_negative"
                    else:
                        key = (
                            ("tp" if prediction else "fn")
                            if truth
                            else ("fp" if prediction else "tn")
                        )
                    counts[key] += 1
                summary[variant][label] = counts
        summary.update(
            cases=len(records),
            no_proposal=sum(r.get("no_proposal", False) for r in records),
            wall_sec=sum(r["wall_sec"] for r in records),
            model_load_sec=model_load_sec,
            peak_gpu_bytes=torch.cuda.max_memory_allocated(),
        )
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary), flush=True)
        return (
            2
            if any(
                "error" in r or any(not c["ok"] for v in r["variants"].values() for c in v["calls"])
                for r in records
            )
            else 0
        )


if __name__ == "__main__":
    raise SystemExit(main())
