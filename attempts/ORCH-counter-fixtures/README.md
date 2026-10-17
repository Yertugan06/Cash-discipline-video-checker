# ORCH-counter - money counter fixture aliases

- Date: 2026-10-18.
- Branch: `orch/counter`, based on `night` at `2c728da`.
- Status: measured correctness correction; not a score improvement.
- Models: unchanged; local numeric perception-cache replay only.

Personal-item events exclude boxes matching a calibrated laptop/counter or repeated
alternative laptop/counter calibration candidates. This removes the money machine's
handbag aliases, including when no counter was calibrated. Х-40's real coat stays caught.

| Run | Before: correct / clean FP / missed | After: correct / clean FP / missed |
|---|---|---|
| Full | 27 / 4 / 9 | 24 / 3 / 13 |
| Drop 0.2 seed 0 | 24 / 4 / 12 | 22 / 3 / 15 |
| Drop 0.2 seed 1 | 28 / 2 / 10 | 25 / 2 / 13 |
| Drop 0.2 seed 2 | 25 / 4 / 11 | 25 / 2 / 13 |

X-1, Х-11, Х-13 and Х-15 lose accidental catches. Clean Х-48 clears. The cache cannot
establish Х-13's cash-to-safe transfer, so K-RECOUNT-BEFORE-SAFE is unchanged. The existing
L-NO-BAG-ON-LEAVE already hits Х-15 at 15 s but is absent from knowledge rule enablement.

Required tests: 101 passed, 1 skipped. Ruff check and format check pass. No other enabled
rule's findings change. Full clip evidence, rejected approaches, signal handoff and
reproduction commands: [REPORT-ORCH.md](../../REPORT-ORCH.md).
