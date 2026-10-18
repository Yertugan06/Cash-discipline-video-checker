#!/usr/bin/env python3
"""CPU-only A22 replay. Only model detections and local CV matches enter the replay."""

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--clips",
        default="4,5,38,39,26,27",
        help="Evaluation selection only; all for all 40 unique files",
    )
    parser.add_argument("--budget-sec", type=float, default=480)
    args = parser.parse_args()
    sys.path.insert(0, str(args.base.resolve()))
    import cv2
    import yaml

    from backend.f1.calibration import calibrate
    from backend.f1.codex import load_codex
    from backend.f1.detector import F1Detector
    from backend.f1.events import build_events
    from backend.f1.perception import load_perception_config
    from backend.f1.rules import Context, evaluate_rules
    from backend.f1.vision_types import Observation, Scene

    cv2.setNumThreads(2)
    spec = importlib.util.spec_from_file_location("a22_temporal_candidate", args.module)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    config = load_perception_config(args.base / "config/perception.yaml")
    codex = load_codex(args.base / "config/f1_codex.yaml")
    enabled = {
        r["rule_id"]
        for r in yaml.safe_load((args.base / "knowledge/rules.yaml").read_text())
        if r.get("enabled")
    }
    # This index selects input files only; no verdict, annotation or timing field is used.
    index = [
        json.loads(s)
        for s in (args.base / "data/prepared/videos.jsonl").read_text().splitlines()
        if s.strip()
    ]
    wanted = None if args.clips == "all" else {int(s) for s in args.clips.split(",")}
    jobs, seen = [], set()
    for row in index:
        number = int(row["original_id"].split("-")[-1])
        if row["sha256"] in seen or (wanted is not None and number not in wanted):
            continue
        seen.add(row["sha256"])
        matches = [
            p
            for p in args.videos.iterdir()
            if p.suffix.lower() == ".mov" and p.stem.replace("Х", "X") == f"X-{number}"
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one video for evaluation input {number}")
        jobs.append((number, row["sha256"], matches[0]))
    args.out.mkdir(parents=True, exist_ok=True)
    metadata = {
        "base": str(args.base),
        "module_sha256": hashlib.sha256(args.module.read_bytes()).hexdigest(),
        "events_module": str(sys.modules["backend.f1.events"].__file__),
        "rules_module": str(sys.modules["backend.f1.rules"].__file__),
        "opencv_version": cv2.__version__,
        "planned_clips": len(jobs),
        "status": "running",
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    deadline = time.monotonic() + args.budget_sec
    results = []
    for number, sha, video in jobs:
        started = time.monotonic()
        files = list((args.cache / sha).glob("*.json"))
        payload = json.loads(max(files, key=lambda p: p.stat().st_mtime).read_text())
        observations = [Observation.model_validate(o) for o in payload["observations"]]
        scene = Scene.model_validate(payload["scene"])
        if scene.candidates:
            scene = calibrate(scene.candidates, args.base / "config/overrides.yaml", sha)
        frames_dir = Path(tempfile.mkdtemp(prefix="a22-cv-"))
        try:
            frames = F1Detector._extract_frames(video, frames_dir, deadline)
            refined, provenance = candidate.refine_cash_tracks(
                frames, scene, observations, deadline
            )
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)
        result = {
            "clip": number,
            "sha256": sha,
            "provenance": provenance,
            "new_samples": sum(
                len(new.detections) - len(old.detections)
                for old, new in zip(observations, refined, strict=True)
            ),
            "rejections": dict(
                Counter(r["reason"] for r in provenance if r["status"] == "stopped")
            ),
        }
        for variant, samples in (("before", observations), ("after", refined)):
            duration = samples[-1].timestamp_sec + 0.5
            runtime_scene = scene.model_copy(deep=True)
            runtime_observations = [o.model_copy(deep=True) for o in samples]
            log = build_events(runtime_scene, runtime_observations, config, 2, duration)
            findings = evaluate_rules(
                Context(codex, log, runtime_observations, runtime_scene, duration)
            )
            result[variant] = {
                "findings": [
                    {"rule_id": f.rule_id, "t": f.timestamp_sec}
                    for f in findings
                    if f.rule_id in enabled
                ],
                "sessions": log.sessions,
                "cash_events": [
                    e.model_dump()
                    for e in log.events
                    if e.type
                    in {
                        "CASH_STATE",
                        "CASH_REASSOCIATED",
                        "HANDOVER",
                        "SESSION_START",
                        "SESSION_END",
                    }
                ],
            }
        result["sec"] = time.monotonic() - started
        results.append(result)
        (args.out / "results.json").write_text(json.dumps(results, indent=2, allow_nan=False))
        print(
            json.dumps({k: result[k] for k in ("clip", "new_samples", "rejections", "sec")}),
            flush=True,
        )
    metadata.update(status="complete", completed_clips=len(results))
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
