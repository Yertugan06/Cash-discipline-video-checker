"""Score a directory of API `DoneJob` JSON outputs (one file per video) with the R1 scorer.

Adapts `DoneJob` shapes to the harness's expected prediction format
(`reasearch1/validation-evidence/harness/score.py`):
``{clip_id: {"verdict": ..., "events": [{"t": ..., "code": ..., "conf": ...}], "runtime_s": ...,
"error": ...}}``, writes it to ``<root>/validation-private/preds/<name>.json``, then runs the
harness's own `score.py` as a subprocess so this module never re-implements its aggregation. The
harness only ever prints aggregate numbers; this module never reads or prints an individual
label.

Usage:
    .venv/bin/python -m eval.run_eval <done_jobs_dir> [--root reasearch1] [--name NAME]
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

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_SCORE = REPO_ROOT / "reasearch1" / "validation-evidence" / "harness" / "score.py"


def clip_id_from_filename(name: str) -> str:
    """'X-12.json' / 'Х-12.mov.json' -> 'X-12'. A file not named after a clip is an error."""
    return parse_clip_id(Path(name).stem)


def to_pred_entry(done_job: dict) -> dict:
    """One `DoneJob`-shaped dict -> one harness prediction entry."""
    verdict = done_job.get("verdict", "no_violation")
    events = [
        {
            "t": v.get("timecode_sec"),
            "code": v.get("rule_id"),
            "conf": None,
        }
        for v in done_job.get("violations", [])
    ]
    error = None
    if done_job.get("status") == "failed":
        error = done_job.get("error", "failed")
    return {"verdict": verdict, "events": events, "runtime_s": None, "error": error}


def build_pred(done_jobs_dir: Path) -> dict[str, dict]:
    """Read every `*.json` file in `done_jobs_dir` as a `DoneJob` and build the harness pred map."""
    pred: dict[str, dict] = {}
    for f in sorted(done_jobs_dir.glob("*.json")):
        clip = clip_id_from_filename(f.name)
        if clip in pred:
            raise ValueError(f"two DoneJob files for {clip} in {done_jobs_dir}")
        data = json.loads(f.read_text(encoding="utf-8"))
        pred[clip] = to_pred_entry(data)
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
    ap.add_argument("--root", type=Path, default=REPO_ROOT / "reasearch1")
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
