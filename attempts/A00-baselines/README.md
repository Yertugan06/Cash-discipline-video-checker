# A00 - Baselines (floors)

- **Date:** 2026-10-17
- **Status:** reference
- **Source:** `archive/research1/problem-validation.md` §2, `validation/validation-evidence/PREREGISTRATION.md`

## Approach

Pixel-free answers every real approach has to beat, scored with the pre-registered scorer
(`validation/validation-evidence/harness/score.py`).

## Results

| Floor | Verdict /40 | Top-1 timecode ±1/2/3/5 s (22 events) |
|---|---|---|
| Always "violation" + top motion peak | 21 (recall 21/21, clean FP 19/19) | 4/6/7/9 |
| Duration threshold, leave-one-out (shortcut, reference only) | 25 | - |
| Relative-position prior (shortcut, reference only) | - | 3/9/12/17 |
| Motion-threshold verdict | 14 | - |

Differences of 2 videos or fewer count as ties (n is small, Wilson intervals about ±20 points).

## Logs

- `validation/validation-evidence/logs/score_F0_blind.txt`
- `validation/validation-evidence/logs/score_all_gtv2.txt`
