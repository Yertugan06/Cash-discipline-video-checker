"""Run one actual local F1 job; export numeric results, never dataset pixels."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget", type=float, default=270)
    args = parser.parse_args()
    if not args.video.is_file() or not args.weights.is_dir() or args.budget <= 0:
        parser.error("Existing video/weights and a positive time budget are required")
    args.out.mkdir(parents=True, exist_ok=False)
    lock_path = Path.home() / ".cache/datathon-workers/gpu.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from backend.config import ROOT, Settings
        from backend.contracts import SamplingPlan
        from backend.f1.detector import F1Detector
        from backend.knowledge import Knowledge
        from backend.media import probe

        info = probe(args.video)
        settings = Settings(
            api_key="a21-local-benchmark",
            rule_scope="detector",
            device="cuda",
            cpu_threads=2,
            reuse_perception=False,
            weights_dir=args.weights,
            work_dir=args.out / "runtime",
            cache_dir=args.out / "perception_cache",
        )
        settings.work_dir.mkdir(parents=True)
        detector = F1Detector(settings, Knowledge.load(ROOT / "knowledge").rules)
        start = time.monotonic()
        plan = SamplingPlan(coarse_t=[], fill_t=[], deadline_monotonic=start + args.budget)
        print(json.dumps({"phase": "started", "video": args.video.name, "cache_reuse": False}), flush=True)
        result = detector.detect(args.video, info, plan)
        seconds = time.monotonic() - start
        assert result.coverage.done > 0
        assert all(0 <= finding.t_anchor <= info.duration_sec for finding in result.findings)
        record = {
            "video": args.video.name,
            "sha256": info.sha256,
            "duration_sec": info.duration_sec,
            "inference_seconds": seconds,
            "cache_reuse": False,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "perception_config_sha256": hashlib.sha256(settings.perception_config.read_bytes()).hexdigest(),
            "models_lock_sha256": hashlib.sha256((ROOT / "models.lock.json").read_bytes()).hexdigest(),
            "result": result.model_dump(mode="json"),
        }
        (args.out / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"phase": "completed", "seconds": round(seconds, 2), "findings": len(result.findings), "coverage": result.coverage.model_dump()}), flush=True)


if __name__ == "__main__":
    main()
