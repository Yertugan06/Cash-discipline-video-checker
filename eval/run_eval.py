"""Score a directory of API `DoneJob` JSON outputs (one file per video) with the R1 scorer.

Adapts `DoneJob` shapes to the harness's expected prediction format
(`validation/validation-evidence/harness/score.py`):
``{clip_id: {"verdict": ..., "events": [{"t": ..., "code": ..., "conf": ...}], "runtime_s": ...,
"error": ...}}``. An event's ``code`` is the primary norm id of the violation's rule in
`knowledge/rules.yaml` (e.g. ``A-DOOR-LOCK`` -> ``14-16-1``), the form the scorer's
`code_match()` compares with the human annotation's norm. It writes the map to
``<root>/validation-private/preds/<name>.json``, then runs the harness's own `score.py` as a
subprocess so this module never re-implements its aggregation. The harness only ever prints
aggregate numbers; this module never reads or prints an individual label.

Usage:
    .venv/bin/python -m eval.run_eval <done_jobs_dir> [--root validation] [--name NAME]
                                       [--split dev|lockbox|all]

`--split lockbox` is for the one-time, human-gated scoring step only (shared brief: "Never use
the lockbox split for any choice"); this tool does not restrict it, but callers should default to
`dev` for anything other than that single approved run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from backend.clip_id import parse_clip_id
from backend.knowledge import Knowledge

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_SCORE = REPO_ROOT / "validation" / "validation-evidence" / "harness" / "score.py"
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


def clip_id_from_filename(name: str) -> str:
    """'X-12.json' / 'Х-12.mov.json' -> 'X-12'. A file not named after a clip is an error."""
    return parse_clip_id(Path(name).stem)


def primary_norm_id(rule_id: str | None, knowledge: Knowledge) -> str:
    """A violation's rule -> the first of its `norm_ids`. A violation without a known rule is an
    error: scoring it with no code would read as a real citation miss."""
    if not rule_id:
        raise ValueError("violation has no rule_id; cannot score its legal citation")
    return knowledge.rule(rule_id).norm_ids[0]


def to_pred_entry(done_job: dict, knowledge: Knowledge) -> dict:
    """One `DoneJob`-shaped dict -> one harness prediction entry."""
    verdict = done_job.get("verdict", "no_violation")
    events = [
        {
            "t": v.get("timecode_sec"),
            "code": primary_norm_id(v.get("rule_id"), knowledge),
            "conf": None,
        }
        for v in done_job.get("violations", [])
    ]
    error = None
    if done_job.get("status") == "failed":
        error = done_job.get("error", "failed")
    return {"verdict": verdict, "events": events, "runtime_s": None, "error": error}


def build_pred(done_jobs_dir: Path, knowledge_root: Path = KNOWLEDGE_ROOT) -> dict[str, dict]:
    """Read every `*.json` file in `done_jobs_dir` as a `DoneJob` and build the harness pred map.

    An optional `<clip>.meta.json` next to a result (the layout `eval.check_outputs` reads, written
    by `eval.export_gateway_run`) gives the upload-to-result `wall_s`, scored as `runtime_s`.
    """
    knowledge = Knowledge.load(knowledge_root)
    pred: dict[str, dict] = {}
    for f in sorted(done_jobs_dir.glob("*.json")):
        if f.name.endswith(".meta.json"):
            continue
        clip = clip_id_from_filename(f.name)
        if clip in pred:
            raise ValueError(f"two DoneJob files for {clip} in {done_jobs_dir}")
        data = json.loads(f.read_text(encoding="utf-8"))
        pred[clip] = entry = to_pred_entry(data, knowledge)
        meta = f.with_name(f"{f.stem}.meta.json")
        if meta.exists():
            entry["runtime_s"] = json.loads(meta.read_text(encoding="utf-8"))["wall_s"]
    return pred


def run_scorer(pred: dict[str, dict], root: Path, name: str, split: str = "dev") -> str:
    """Write `pred` to `<root>/validation-private/preds/<name>.json` and run the harness scorer.

    Returns the scorer's stdout (aggregate numbers only, by the harness's own design).
    """
    if not HARNESS_SCORE.exists():
        raise FileNotFoundError(f"harness score.py not found at {HARNESS_SCORE}")
    preds_dir = root / "validation-private" / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)
    (preds_dir / f"{name}.json").write_text(json.dumps(pred), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-I", str(HARNESS_SCORE), str(root), name, "--split", split],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("done_jobs_dir", type=Path)
    ap.add_argument("--root", type=Path, default=REPO_ROOT / "validation")
    ap.add_argument("--name", default="api_run_eval")
    ap.add_argument("--split", choices=["dev", "lockbox", "all"], default="dev")
    args = ap.parse_args(argv)

    pred = build_pred(args.done_jobs_dir)
    if not pred:
        print(f"no DoneJob files found under {args.done_jobs_dir}", file=sys.stderr)
        sys.exit(1)
    report = run_scorer(pred, args.root, args.name, args.split)
    print(report)


if __name__ == "__main__":
    main()
