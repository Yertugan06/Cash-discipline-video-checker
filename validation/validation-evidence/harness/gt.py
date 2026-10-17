"""Retired 2026-10-18. The ground-truth builder now lives in `eval/ground_truth.py` (the one place that
reads organizer labels and human annotations), reading the team data root described in `eval/data.py`.

    .venv/bin/python -m eval.ground_truth            # build, report discrepancies, check the split
    .venv/bin/python -m eval.ground_truth --write    # rewrite validation/validation-private/gt.json

The previous version is in git history (`git log -p -- validation/validation-evidence/harness/gt.py`).
The builder prints aggregate counts only. The data root is managed by `eval.data`.
"""
import sys

sys.exit('gt.py is retired: run `python -m eval.ground_truth` from the repo root (see this file).')
