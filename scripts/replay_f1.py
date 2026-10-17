"""Re-run the F1 event builder and rules on cached perception, without the GPU.

`run` goes inside the checker container (it needs cv2 and the cache volume). It re-calibrates
from the cached candidates when the cache has them, then prints one JSON line per video:

    docker exec -i -w /app datathon26-checker-1 python - run < scripts/replay_f1.py > replay.jsonl

To try uncommitted code on the same cache, mount the tree instead (read-only):

    docker run --rm --entrypoint '' -v datathon26_work:/app/runtime:ro -v $PWD:/work:ro \
      -w /work -e PYTHONPATH=/work -e API_KEY=x forte-cash-checker:cuda \
      python scripts/replay_f1.py run > replay.jsonl

With `--videos-dir` (the clips the cache was made from, mounted into the container) the leave
rules take their items from desk change instead of the detector's labels (attempt A18,
`backend/f1/desk_objects.py`); each line then also lists the clip's desk objects:

    docker run ... -v ~/data/open/videos:/videos:ro ... python scripts/replay_f1.py run \
      --videos-dir /videos > replay-a18.jsonl

`--mirror`, `--zoom 0.8` and `--drop 0.2` replay the clips as another camera or a weaker
detector would report them (mirrored, filmed from farther away, 20% of object detections lost).
A verdict that changes points at a rule tied to one camera set-up (robustness check, no GPU
or video needed).

`score` runs anywhere and joins those lines with the organizer labels:

    python scripts/replay_f1.py score replay.jsonl --labels data/prepared/videos.jsonl

`state` turns a replay into a saved run for the gateway's `/compare` page:

    python scripts/replay_f1.py state replay.jsonl --labels data/prepared/videos.jsonl \
      --out state.replay-<name>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def desk_objects_for(video: Path, observations, scene, log) -> list | None:
    import shutil
    import tempfile
    import time

    import cv2

    from backend.f1.desk_objects import build_desk_objects
    from backend.f1.detector import F1Detector

    frames_dir = Path(tempfile.mkdtemp(prefix="a18-frames-"))
    try:
        # The same 2 fps decode the detector ran, so frame i is observation i.
        frames = F1Detector._extract_frames(video, frames_dir, time.monotonic() + 600)
        images = (cv2.imread(str(frame)) for frame in frames)
        return build_desk_objects(images, observations, scene, log)
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


def transform_detection(detection: dict, point) -> dict:
    x1, y1, x2, y2 = detection["box"]
    (a, b), (c, d) = point(x1, y1), point(x2, y2)
    moved = {**detection, "box": [min(a, c), min(b, d), max(a, c), max(b, d)]}
    for key in ("body", "hands"):
        if detection.get(key):
            moved[key] = [[*point(x, y), score] for x, y, score in detection[key]]
    return moved


def perturb_payload(payload: dict, mirror: bool, zoom: float, drop: float, seed: str) -> dict:
    """The same clip as another camera would report it: mirrored left to right, zoomed about the
    image centre (zoom < 1 = filmed from farther away), and/or with a share of the non-person
    detections lost (a weaker detector). Deterministic per clip for a given seed."""
    import random

    def point(x: float, y: float) -> tuple[float, float]:
        x = 1 - x if mirror else x
        return 0.5 + (x - 0.5) * zoom, 0.5 + (y - 0.5) * zoom

    rng = random.Random(seed)
    scene = dict(payload["scene"])
    scene["candidates"] = [transform_detection(d, point) for d in scene.get("candidates", [])]
    scene["objects"] = {
        k: transform_detection(d, point) for k, d in scene.get("objects", {}).items()
    }
    scene["zones"] = {
        k: [list(point(x, y)) for x, y in v] for k, v in scene.get("zones", {}).items()
    }
    if scene.get("cashier_direction") and mirror:
        dx, dy = scene["cashier_direction"]
        scene["cashier_direction"] = [-dx, dy]
    observations = [
        {
            **o,
            "detections": [
                transform_detection(d, point)
                for d in o["detections"]
                if d["label"] == "person" or rng.random() >= drop
            ],
        }
        for o in payload["observations"]
    ]
    return {**payload, "scene": scene, "observations": observations}


def run(
    cache_dir: Path,
    videos_dir: Path | None,
    mirror: bool = False,
    zoom: float = 1.0,
    drop: float = 0.0,
    seed: int = 0,
) -> None:
    import yaml

    from backend.config import ROOT
    from backend.f1.calibration import calibrate, video_checksum
    from backend.f1.codex import load_codex
    from backend.f1.detector import FPS
    from backend.f1.events import build_events
    from backend.f1.perception import load_perception_config
    from backend.f1.rules import Context, evaluate_rules
    from backend.f1.vision_types import Observation, Scene

    config = load_perception_config(ROOT / "config" / "perception.yaml")
    codex = load_codex(ROOT / "config" / "f1_codex.yaml")
    rules = yaml.safe_load((ROOT / "knowledge" / "rules.yaml").read_text(encoding="utf-8"))
    enabled = {rule["rule_id"] for rule in rules if rule.get("enabled")}
    videos = {}
    if videos_dir:
        videos = {video_checksum(p): p for p in sorted(videos_dir.iterdir()) if p.is_file()}
    for video_dir in sorted(p for p in cache_dir.iterdir() if p.is_dir()):
        files = list(video_dir.glob("*.json"))
        if not files:
            continue
        payload = json.loads(max(files, key=lambda p: p.stat().st_mtime).read_text())
        if mirror or zoom != 1.0 or drop:
            payload = perturb_payload(payload, mirror, zoom, drop, f"{video_dir.name}:{seed}")
        scene = Scene.model_validate(payload["scene"])
        if scene.candidates:
            scene = calibrate(scene.candidates, ROOT / "config" / "overrides.yaml", video_dir.name)
        observations = [Observation.model_validate(o) for o in payload["observations"]]
        duration = observations[-1].timestamp_sec + 1 / FPS
        log = build_events(scene, observations, config, FPS, duration)
        desk_objects = None
        if videos_dir:
            if video_dir.name not in videos:
                print(f"no video for cache entry {video_dir.name[:12]}", file=sys.stderr)
                continue
            desk_objects = desk_objects_for(videos[video_dir.name], observations, scene, log)
        findings = evaluate_rules(Context(codex, log, observations, scene, duration, desk_objects))
        record = {
            "sha256": video_dir.name,
            "desk": scene.objects["desk"].box if "desk" in scene.objects else None,
            "findings": [
                {"rule_id": f.rule_id, "t": round(f.timestamp_sec, 1)}
                for f in findings
                if f.rule_id in enabled
            ],
        }
        if desk_objects is not None:
            record["desk_objects"] = [
                {
                    "id": o.track_id,
                    "t": [o.seen[0], o.seen[-1]],
                    "frames": len(o.seen),
                    "box": [round(v, 3) for v in o.box],
                    "origin": o.origin,
                    "counted": o.counted,
                    "detector": o.detector_kind,
                    "kind": o.kind,
                }
                for o in desk_objects
            ]
        print(json.dumps(record), flush=True)


def score(results: Path, labels: Path) -> None:
    videos = {}
    for line in labels.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            videos[row["sha256"]] = row
    totals = {
        "videos": 0,
        "correct": 0,
        "clean_false_alarm": 0,
        "missed": 0,
        "outsider_on_clean": 0,
    }
    for line in results.read_text(encoding="utf-8").splitlines():
        result = json.loads(line)
        row = videos.get(result["sha256"])
        if row is None:
            print(f"unlabelled cache entry {result['sha256'][:12]}", file=sys.stderr)
            continue
        label = row["organizer_verdict"]
        rule_ids = sorted({f["rule_id"] for f in result["findings"]})
        verdict = "violation" if rule_ids else "no_violation"
        totals["videos"] += 1
        totals["correct"] += verdict == label
        totals["clean_false_alarm"] += label == "no_violation" and verdict == "violation"
        totals["missed"] += label == "violation" and verdict == "no_violation"
        totals["outsider_on_clean"] += label == "no_violation" and "A-OUTSIDER-ZONE" in rule_ids
        mark = "ok " if verdict == label else "BAD"
        found = ", ".join(f"{f['rule_id']}@{f['t']}" for f in result["findings"]) or "-"
        print(f"{mark} {row['original_id']:6} label={label:13} {found}")
    print(json.dumps(totals))


def to_state(results: Path, labels: Path, out: Path) -> None:
    """Write a replay as a gateway state file, so `/compare` shows it next to the live runs
    (save it as `state.<name>.json` beside the gateway's STATE_FILE)."""
    by_sha = {
        json.loads(line)["sha256"]: json.loads(line) for line in results.read_text().splitlines()
    }
    items = []
    for line in labels.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        result = by_sha.get(row["sha256"])
        if result is None:
            continue
        violations = [
            {"rule_id": f["rule_id"], "type": f["rule_id"], "timecode_sec": f["t"]}
            for f in result["findings"]
        ]
        items.append(
            {
                "id": row["sha256"][:32],
                "name": Path(row["path"]).name,
                "source": "folder",
                "status": "done",
                "verdict": "violation" if violations else "no_violation",
                "label": row["organizer_verdict"],
                "result": {"violations": violations},
            }
        )
    out.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} items -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--cache-dir", type=Path, default=Path("/app/runtime/perception_cache"))
    run_parser.add_argument("--videos-dir", type=Path, default=None)
    run_parser.add_argument("--mirror", action="store_true")
    run_parser.add_argument("--zoom", type=float, default=1.0)
    run_parser.add_argument("--drop", type=float, default=0.0)
    run_parser.add_argument("--seed", type=int, default=0)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("results", type=Path)
    score_parser.add_argument("--labels", type=Path, required=True)
    state_parser = sub.add_parser("state")
    state_parser.add_argument("results", type=Path)
    state_parser.add_argument("--labels", type=Path, required=True)
    state_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "run":
        if (args.mirror or args.zoom != 1.0 or args.drop) and args.videos_dir:
            parser.error("perturbations move cached boxes only; they can't go with --videos-dir")
        run(args.cache_dir, args.videos_dir, args.mirror, args.zoom, args.drop, args.seed)
    elif args.mode == "score":
        score(args.results, args.labels)
    else:
        to_state(args.results, args.labels, args.out)


if __name__ == "__main__":
    main()
