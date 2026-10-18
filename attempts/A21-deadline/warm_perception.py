"""Precompute one temporary evaluation shard with the canonical local F1 models."""

from __future__ import annotations

import argparse
import fcntl
import json
import tempfile
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from backend.config import Settings
    from backend.f1.detector import FPS, F1Detector
    from backend.f1.perception import perceive_video
    from backend.media import probe

    rows = json.loads(args.manifest.read_text())["videos"]
    assert len({row["sha256"] for row in rows}) == len(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        api_key="a21-preprocessing",
        rule_scope="detector",
        device="cuda",
        cpu_threads=2,
        reuse_perception=False,
        weights_dir=args.weights,
        work_dir=args.out,
        cache_dir=args.out / "perception_cache",
    )
    lock_path = Path.home() / ".cache/datathon-workers/gpu.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows, 1):
        name = row["filename"]
        if Path(name).name != name:
            raise ValueError("Shard filenames must be plain basenames")
        video = args.videos / name
        record = {"video": name, "sha256": row["sha256"], "index": index, "total": len(rows)}
        print(json.dumps({**record, "phase": "waiting_for_gpu"}), flush=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.monotonic()
            try:
                info = probe(video)
                if info.sha256 != row["sha256"]:
                    raise ValueError("Video hash does not match the frozen shard")
                deadline = started + 270
                with tempfile.TemporaryDirectory(prefix="a21-frames-", dir=args.out) as tmp:
                    frames = F1Detector._extract_frames(video, Path(tmp), deadline)
                    scene, observations, config = perceive_video(
                        frames, info.sha256, settings, deadline, FPS
                    )
                record.update(status="done", observations=len(observations), cache_hit=bool(config.get("cache_hit")), warnings=scene.warnings)
            except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            record["seconds"] = round(time.monotonic() - started, 3)
        with (args.out / "progress.jsonl").open("a") as output:
            output.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
