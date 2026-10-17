# ORCH-personal - Preserve personal-item intervals through brief detector gaps

- **Date / who:** 2026-10-18, personal-items implementer
- **Status:** measured offline, not deployed
- **Where it ran:** `orch/personal`, local perception-cache replay, no GPU
- **Models:** A17 cached detections, unchanged

The event builder previously treated every missing object detection as removal from the
desk. Keep an existing personal-item track active through the configured 1.2 s track-loss
window; visible carried/off-desk evidence ends it. Count no trailing uncertainty toward
the sustained-duration threshold. Track IDs, thresholds and prompts are unchanged.

| Variant | Correct /40 | Clean false alarms | Missed |
|---|---:|---:|---:|
| A17 baseline | 25 | 5 | 10 |
| Personal-item detection gaps | 26 | 5 | 9 |
| Also suppress calibrated fixtures, rejected | 23 | 5 | 12 |
| Also broaden worn-coat overlap, rejected | 26 | 4 | 10 |

Only Х-40's verdict improves, at 19.5 s versus organizer 17 s. No other verdict changes.
Protected violation clips stay caught, but their personal-item hits mostly concern work
tools and do not explain the spreadsheet violations. Removing those accidental hits is
not safe for whole-video recall until the corresponding rules detect their actual events.

Full clip-by-clip evidence, timing offsets, rejected alternatives, reproduction commands,
files and test results: [REPORT-ORCH.md](../../REPORT-ORCH.md).

Required tests: 82 passed, 1 existing full-model test skipped. Ruff check and format check
pass for changed Python files. No dataset frames/images, VM or network were accessed.
