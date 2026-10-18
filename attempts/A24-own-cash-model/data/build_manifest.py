"""Build the frozen A24 presence cohort from text only; never decode video or import A13."""

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TRAIN = {38, 26, 10, 2, 14, 23, 29, 32}
PROBE = {4, 13, 33, 40}
POSITIVES = {4, 38, 26, 10, 2, 13, 14}
TIMES = {4: 56, 38: 30, 26: 15, 10: 8, 2: 9.8, 13: 30, 14: 60, 23: 16, 29: 16, 32: 2, 33: 2, 40: 18}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a13", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    frames = None
    for node in ast.parse(args.a13.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FRAMES" for target in node.targets
        ):
            frames = ast.literal_eval(node.value)
            break
    if frames is None:
        raise ValueError("A13 FRAMES must be a literal assignment")
    videos = [json.loads(line) for line in args.videos.read_text().splitlines() if line.strip()]
    by_number = {int(row["video_id"].split("-")[-1]): row for row in videos}
    duplicate_hashes = defaultdict(set)
    for row in videos:
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid original video SHA-256")
        if row["duplicate_group"]:
            duplicate_hashes[row["duplicate_group"]].add(row["sha256"])
    if any(len(hashes) != 1 for hashes in duplicate_hashes.values()):
        raise ValueError("Duplicate group has inconsistent original hashes; review before fitting")
    records = []
    for clip, timestamp, note, expected in frames:
        if "cash" not in expected:
            continue
        number = int(clip.split("-")[-1])
        records.append(
            dict(
                clip=f"X-{number}",
                t=timestamp,
                cash_visible=expected["cash"],
                split="train" if number in TRAIN else "probe",
                video_sha256=by_number[number]["sha256"],
                group_sha256=by_number[number]["sha256"],
                label_source="A13 manual presence",
                note=note,
            )
        )
    records.append(
        dict(
            clip="X-40",
            t=18,
            cash_visible=False,
            split="probe",
            video_sha256=by_number[40]["sha256"],
            group_sha256=by_number[40]["sha256"],
            label_source="user confirmation",
            note="No cash; only coat and bag.",
        )
    )
    train_groups = {row["group_sha256"] for row in records if row["split"] == "train"}
    probe_groups = {row["group_sha256"] for row in records if row["split"] == "probe"}
    assert len(records) == 12 and {int(r["clip"].split("-")[-1]) for r in records} == TRAIN | PROBE
    assert len({(r["clip"], r["t"]) for r in records}) == 12
    assert all(type(r["cash_visible"]) is bool for r in records)
    assert all(r["cash_visible"] == (int(r["clip"].split("-")[-1]) in POSITIVES) for r in records)
    assert all(r["t"] == TIMES[int(r["clip"].split("-")[-1])] for r in records)
    assert {int(r["clip"].split("-")[-1]) for r in records if r["split"] == "train"} == TRAIN
    assert {int(r["clip"].split("-")[-1]) for r in records if r["split"] == "probe"} == PROBE
    assert not train_groups & probe_groups
    counts = Counter((r["split"], r["cash_visible"]) for r in records)
    assert counts == {
        ("train", True): 5,
        ("train", False): 3,
        ("probe", True): 2,
        ("probe", False): 2,
    }
    manifest = dict(
        schema_version=1, source_commit="4a3b9ea", task="workspace_cash_presence", records=records
    )
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "label-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    provenance = dict(
        source_a13_sha256=hashlib.sha256(args.a13.read_bytes()).hexdigest(),
        source_videos_jsonl_sha256=hashlib.sha256(args.videos.read_bytes()).hexdigest(),
        manifest_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        counts={
            f"{split}_{'positive' if cash else 'negative'}": n
            for (split, cash), n in sorted(counts.items())
        },
        train_groups=len(train_groups),
        probe_groups=len(probe_groups),
        group_overlap=0,
        duplicate_aliases={
            group: [row["original_id"] for row in videos if row["duplicate_group"] == group]
            for group in duplicate_hashes
        },
        checks="PASS: exact cohort, labels, timestamps, split8/4 and no SHA-group overlap",
        pixels_decoded=0,
        training_run=False,
    )
    (args.out / "audit.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance))


if __name__ == "__main__":
    main()
