"""Retired 2026-10-18. `validation-private/split.json` is frozen and must never be redrawn.
`python -m eval.ground_truth` re-derives it from the current gt.json with the original algorithm
(`eval.ground_truth.draw_split`) and fails if it no longer matches. The previous version is in
git history.
"""
import sys

sys.exit('split.py is retired: the split is frozen; check it with `python -m eval.ground_truth`.')
