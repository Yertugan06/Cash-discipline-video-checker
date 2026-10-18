"""Check a directory of API job results (`<clip>.json`, optional `<clip>.meta.json` with `wall_s`)
against the jury contract (task.md §10) and the organizer labels.

Per clip it prints only structured facts, never a description or a frame: whether the JSON is a
valid `DoneJob`, the verdict against the organizer label of that very clip (duplicates keep their
own label), each finding's rule, its distance to the nearest organizer second, whether its 1-3
evidence frames decode as JPEG, whether its description template was fully filled, its citation
status, and the wall time from upload to result (the jury allows 300 s).

Lockbox clips are refused unless --allow-lockbox is given (shared brief: never use the lockbox
for any choice).

    .venv/bin/python -m eval.check_outputs <dir> [--allow-lockbox]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from backend.clip_id import clip_number, parse_clip_id
from backend.contracts import DoneJob, FailedJob
from eval.ground_truth import DEFAULT_OUT

JURY_LIMIT_S = 300.0


def _is_jpeg(b64: str) -> bool:
    try:
        return base64.b64decode(b64, validate=True)[:3] == b"\xff\xd8\xff"
    except (binascii.Error, ValueError):
        return False


def organizer_label(gt: dict[str, dict], clip: str) -> tuple[str, dict]:
    """(video key, this clip's own organizer label)."""
    for key, video in gt.items():
        for f in video["files"]:
            if f["clip_id"] == clip:
                return key, f["organizer"]
    raise KeyError(f"{clip} is not in gt.json")


def check_clip(raw: dict, label: dict, wall_s: float | None) -> dict:
    row: dict = {"wall_s": wall_s, "over_limit": wall_s is not None and wall_s > JURY_LIMIT_S}
    if raw.get("status") == "failed":
        try:
            FailedJob.model_validate(raw)
            row.update(schema="ok (failed job)", outcome="FAILED", findings=[])
        except ValidationError:
            row.update(schema="INVALID", outcome="FAILED", findings=[])
        return row
    try:
        job = DoneJob.model_validate(raw)
    except ValidationError as exc:
        row.update(schema=f"INVALID ({exc.error_count()} errors)", outcome="?", findings=[])
        return row
    predicted, actual = job.verdict == "violation", label["violation"]
    row["schema"] = "ok"
    row["outcome"] = ("TP" if actual else "FP") if predicted else ("FN" if actual else "TN")
    row["verdict_consistent"] = predicted == bool(job.violations)
    row["findings"] = [
        {
            "rule_id": v.rule_id,
            "t": v.timecode_sec,
            "delta_s": min((abs(v.timecode_sec - t) for t in label["times"]), default=None),
            "frames": len(v.evidence_frames),
            "frames_jpeg": all(_is_jpeg(f.image_base64) for f in v.evidence_frames),
            "description_filled": bool(v.description.strip())
            and "{" not in v.description
            and "}" not in v.description,
            "type_set": bool(v.type.strip()),
            "citation": v.citation_status,
            "has_source": bool(v.source and v.source_url),
        }
        for v in job.violations
    ]
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("results", type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--allow-lockbox", action="store_true")
    args = ap.parse_args(argv)

    gt = json.loads((args.out / "gt.json").read_text(encoding="utf-8"))
    split = json.loads((args.out / "split.json").read_text(encoding="utf-8"))
    paths = [p for p in args.results.glob("*.json") if not p.name.endswith(".meta.json")]
    rows = {}
    for path in sorted(paths, key=lambda p: clip_number(p.stem)):
        clip = parse_clip_id(path.stem)
        key, label = organizer_label(gt, clip)
        if split[key] == "lockbox" and not args.allow_lockbox:
            print(f"{clip}: lockbox clip, skipped (pass --allow-lockbox for the final gated run)")
            continue
        meta = path.with_name(f"{path.stem}.meta.json")
        wall = json.loads(meta.read_text())["wall_s"] if meta.exists() else None
        rows[clip] = row = check_clip(json.loads(path.read_text(encoding="utf-8")), label, wall)
        wall_txt = f"{wall:.0f}s" if wall is not None else "?"
        print(f"{clip} [{split[key]}] {row['outcome']} schema={row['schema']} time={wall_txt}")
        for f in row["findings"]:
            delta = f"{f['delta_s']:.1f}s" if f["delta_s"] is not None else "-"
            print(
                f"    {f['rule_id']} t={f['t']:.1f} Δ={delta} frames={f['frames']}"
                f"{'' if f['frames_jpeg'] else ' NOT-JPEG'}"
                f"{'' if f['description_filled'] else ' DESCRIPTION-UNFILLED'}"
                f"{'' if f['type_set'] else ' NO-TYPE'} cite={f['citation']}"
                f"{'' if f['has_source'] else ' NO-SOURCE'}"
            )
    outcomes = [r["outcome"] for r in rows.values()]
    deltas = [
        min(f["delta_s"] for f in r["findings"] if f["delta_s"] is not None)
        for r in rows.values()
        if r["outcome"] == "TP" and any(f["delta_s"] is not None for f in r["findings"])
    ]
    print(
        "summary: "
        + " ".join(f"{o}={outcomes.count(o)}" for o in ("TP", "FN", "FP", "TN", "FAILED", "?"))
        + f" | best finding within ±1s {sum(d <= 1 for d in deltas)}/{outcomes.count('TP')},"
        f" ±3s {sum(d <= 3 for d in deltas)}/{outcomes.count('TP')}"
        + f" | over {JURY_LIMIT_S:.0f}s: {sum(r['over_limit'] for r in rows.values())}"
        + f" | schema invalid: {sum(r['schema'].startswith('INVALID') for r in rows.values())}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
