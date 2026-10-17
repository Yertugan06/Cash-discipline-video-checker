# verify/ -- historical, not maintained

A one-off independent audit (2026-10-17) of the original harness `gt.py`, `split.py` and
`score.py`; see `VERIFICATION_REPORT.md`. These scripts re-implement the ground-truth logic on
purpose and expect the data layout of that day (`data/open/...`, `data/validation-private/...`,
a hard-coded checkout path), so they no longer run as-is.

They are a record, not a source of truth. The ground truth is built and checked by
`python -m eval.ground_truth` (see `eval/README.md`). Known divergence: `verify_gt.py` reads the
one minutes-and-seconds organizer timecode as two events; the authoritative parser
(`eval.ground_truth.parse_timecode`) reads it as one.
