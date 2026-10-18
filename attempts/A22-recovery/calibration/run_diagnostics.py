"""CPU-only numeric diagnostics against the shared A22 base; never opens images."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path


def checksum(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    sys.path.insert(0, str(args.base.resolve()))
    from backend.f1 import events
    from backend.f1.calibration import calibrate
    from backend.f1.perception import load_perception_config
    from backend.f1.vision_types import Observation, Scene, overlap

    if not Path(events.__file__).is_relative_to(args.base.resolve()):
        raise RuntimeError("diagnostics must use shared A22 base, not old dirty worker sources")
    spec = importlib.util.spec_from_file_location("backend.f1.fixture_evidence", args.candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.out.mkdir(parents=True, exist_ok=True)
    videos: dict[str, list[str]] = {}
    for video in sorted(args.videos.iterdir()):
        if video.suffix.lower() in {".mov", ".mp4"}:
            videos.setdefault(checksum(video), []).append(video.stem)
    config = load_perception_config(args.base / "config/perception.yaml")
    summaries, csv_rows = [], []
    total = Counter()
    for directory in sorted(p for p in args.cache.iterdir() if p.is_dir()):
        cache = max(directory.glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        payload = json.loads(cache.read_text())
        cached_scene = Scene.model_validate(payload["scene"])
        scene = (
            calibrate(cached_scene.candidates, args.base / "config/overrides.yaml", directory.name)
            if cached_scene.candidates
            else cached_scene
        )
        observations = [Observation.model_validate(o) for o in payload["observations"]]
        log = events.build_events(
            scene, observations, config, 2, observations[-1].timestamp_sec + 0.5
        )
        rows = module.fixture_evidence(scene, observations)
        counts = Counter(samples=len(rows))
        disagreements = 0
        with gzip.open(args.out / f"{directory.name}.jsonl.gz", "wt", encoding="utf-8") as output:
            for observation, row in zip(observations, rows, strict=True):
                output.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n")
                for person in row["people"]:
                    counts["people_samples"] += 1
                    counts["body_wrists_reliable"] += sum(
                        w["reliable"] for w in person["wrists"].values()
                    )
                    counts["body_wrists_outside_person"] += sum(
                        w["reason"] == "wrist_outside_person_box" for w in person["wrists"].values()
                    )
                    if person["role"] != "cashier":
                        continue
                    counts["cashier_samples"] += 1
                    safe = person["fixtures"]["safe"]
                    counter = person["fixtures"]["counter"]
                    laptop = person["fixtures"]["laptop"]
                    old_person = next(
                        d for d in observation.detections if d.track_id == person["track_id"]
                    )
                    legacy = events.safe_attended(scene, old_person)
                    disagreements += legacy != bool(safe["legacy_near"])
                    reliable = sum(w["reliable"] for w in person["wrists"].values())
                    counts["legacy_safe_attended"] += legacy
                    counts["safe_direct_wrist_contact"] += bool(safe["direct_body_wrists"])
                    counts["safe_exclusive_wrist_contact"] += bool(safe["exclusive_body_wrists"])
                    counts["safe_ambiguous_projection"] += (
                        safe["contact_evidence"] == "ambiguous_projection"
                    )
                    counts["safe_contact_unknown"] += safe["contact_evidence"] == "unknown"
                    counts["legacy_near_no_direct_wrist_support"] += (
                        legacy and not safe["direct_body_wrists"]
                    )
                    counts["legacy_near_two_reliable_wrists_outside"] += (
                        legacy and reliable == 2 and not safe["direct_body_wrists"]
                    )
                    counts["legacy_near_incomplete_wrists"] += legacy and reliable < 2
                    counts["legacy_near_seated"] += (
                        legacy and person["posture"]["value"] == "seated"
                    )
                    counts["legacy_near_counter_running"] += (
                        legacy and counter["classifier_state"]["value"] == "running"
                    )
                    counts["legacy_near_competing_exclusive_contact"] += legacy and bool(
                        safe["other_fixture_exclusive_contacts"]
                    )
                    csv_rows.append(
                        {
                            "sha256": directory.name,
                            "videos": ",".join(videos.get(directory.name, [])),
                            "t": row["t"],
                            "actor": person["track_id"],
                            "bbox_score": person["bbox_score"],
                            "legacy_attended": legacy,
                            "legacy_center_near": safe["near_person_center"],
                            "legacy_hand_near": safe["near_legacy_hand_points"],
                            "legacy_hand_points": person["legacy_hand_point_count"],
                            "reliable_wrists": reliable,
                            "safe_contact": safe["contact_evidence"],
                            "safe_wrists": ",".join(safe["direct_body_wrists"]),
                            "safe_finger_landmarks": safe["hand_landmarks_inside"],
                            "posture": person["posture"]["value"],
                            "posture_score": person["posture"]["score"],
                            "posture_margin": person["posture"]["margin"],
                            "counter_state": counter["classifier_state"]["value"],
                            "counter_score": counter["classifier_state"]["score"],
                            "counter_wrists": ",".join(counter["exclusive_body_wrists"]),
                            "laptop_state": laptop["classifier_state"]["value"],
                            "laptop_wrists": ",".join(laptop["exclusive_body_wrists"]),
                            "safe_wrist_box_gaps": json.dumps(
                                safe["wrist_box_distance_reference_units"]
                            ),
                            "counter_wrist_box_gaps": json.dumps(
                                counter["wrist_box_distance_reference_units"]
                            ),
                            "laptop_wrist_box_gaps": json.dumps(
                                laptop["wrist_box_distance_reference_units"]
                            ),
                            "left": json.dumps(person["wrists"]["left"]),
                            "right": json.dumps(person["wrists"]["right"]),
                        }
                    )
        total.update(counts)
        geometry = rows[0]["calibration"]
        safe = scene.objects.get("safe")
        scale = scene.scaled_distance(1)
        padded = None
        if safe:
            x1, y1, x2, y2 = safe.box
            padded = (
                max(0, x1 - 0.05 * scale),
                max(0, y1 - 0.05 * scale),
                min(1, x2 + 0.05 * scale),
                min(1, y2 + 0.05 * scale),
            )
        summaries.append(
            {
                "sha256": directory.name,
                "videos": videos.get(directory.name, []),
                "cache": str(cache),
                "cache_sha256": checksum(cache),
                "counts": dict(counts),
                "calibration": geometry,
                "cached_scene_boxes": {k: list(v.box) for k, v in cached_scene.objects.items()},
                "safe_expanded_hand_box": padded,
                "safe_expanded_overlaps": {
                    k: overlap(padded, v.box)
                    for k, v in scene.objects.items()
                    if padded and k in {"laptop", "counter"}
                },
                "legacy_geometry_reproduction_mismatches": disagreements,
                "event_roles_covered": log.coverage.get("roles"),
                "classifier_scope": "raw input CLIP states; no new inference or correctness labels",
            }
        )
    if csv_rows:
        with (args.out / "cashier_samples.csv").open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(csv_rows)
    summary = {
        "base": str(args.base),
        "events_source": events.__file__,
        "source_base_commit": "5fae84bc10415111a04b5982d156727ca80f788a",
        "candidate_sha256": checksum(args.candidate),
        "videos_are_diagnostic_names_only": True,
        "clips": len(summaries),
        "aggregate": dict(total),
        "per_clip": summaries,
        "elapsed_s": round(time.monotonic() - started, 3),
        "limits": (
            "All 40 clips influenced development. No attendance accuracy, held-out or score claim."
        ),
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)
    )
    print(
        json.dumps({k: v for k, v in summary.items() if k not in {"per_clip"}}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
