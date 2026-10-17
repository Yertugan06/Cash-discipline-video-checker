"""Exercise the production model adapters on synthetic pixels, with timings and logs."""

import argparse
import json
import logging
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--weights", type=Path, default=ROOT / "weights")
    parser.add_argument("--out", type=Path, default=ROOT / "reports/model-check")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(args.out / "run.log")],
        force=True,
    )
    log = logging.getLogger("model-check")
    report = {
        "status": "running",
        "input": "synthetic RGB image, 464x848; no bank footage",
        "purpose": "execution and timing check; does not measure detection accuracy",
        "requested_device": args.device,
        "python": platform.python_version(),
        "repeats": args.repeats,
        "stages": {},
    }
    started = time.perf_counter()
    try:
        import numpy as np
        from PIL import Image

        from backend.f1.perception import LocalModels, load_perception_config
        from backend.f1.vision_types import Detection

        log.info("Loading pinned RT-DETR, OWLv2, CLIP and RTMPose checkpoints")
        load_started = time.perf_counter()
        config = load_perception_config(ROOT / "config/perception.yaml")
        models = LocalModels(args.weights, args.device, 4, config)
        torch = models.torch

        def synchronize():
            if models.device == "cuda":
                torch.cuda.synchronize()

        synchronize()
        report.update(
            device=models.device,
            pose_device=models.pose_device,
            torch=torch.__version__,
            cuda_runtime=torch.version.cuda,
            gpu=torch.cuda.get_device_name() if models.device == "cuda" else None,
            load_sec=round(time.perf_counter() - load_started, 4),
            checkpoints=json.loads((ROOT / "models.lock.json").read_text())["models"],
        )
        log.info(
            "Models loaded in %.2f s; Torch=%s; RTMPose=%s",
            report["load_sec"],
            models.device,
            models.pose_device,
        )
        image = Image.new("RGB", (464, 848), (120, 125, 130))
        pixels = np.asarray(image)
        person = Detection(label="person", score=1, box=(0.1, 0.1, 0.9, 0.9))
        stages = {
            "person": lambda: len(models.people(image)),
            "scene": lambda: len(models.objects(image, config["scene_prompts"])),
            "objects": lambda: len(models.objects(image, config["object_prompts"])),
            "state": lambda: {
                family: models.state(image, family).model_dump()
                for family in config["state_prompts"]
            },
            "pose": lambda: models.pose(pixels, person),
        }
        for name, operation in stages.items():
            log.info("%s: warm-up", name)
            operation()
            synchronize()
            times = []
            for index in range(args.repeats):
                begin = time.perf_counter()
                output = operation()
                synchronize()
                elapsed = time.perf_counter() - begin
                times.append(elapsed)
                log.info(
                    "%s: pass %d/%d completed in %.4f s", name, index + 1, args.repeats, elapsed
                )
            if name == "pose":
                if len(person.body) != 17 or len(person.hands) != 42:
                    raise ValueError("RTMPose did not return 17 body and 42 hand points")
                output = {"body_points": len(person.body), "hand_points": len(person.hands)}
            report["stages"][name] = {
                "mean_sec": round(statistics.mean(times), 4),
                "min_sec": round(min(times), 4),
                "max_sec": round(max(times), 4),
                "output": output,
            }
        if models.device == "cuda":
            report["peak_torch_memory_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        report["status"] = "passed"
        log.info("All production model adapters passed execution checks")
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        log.exception("Model check failed")
        raise
    finally:
        report["runtime_sec"] = round(time.perf_counter() - started, 4)
        (args.out / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        log.info("Result saved to %s", args.out / "result.json")


if __name__ == "__main__":
    main()
