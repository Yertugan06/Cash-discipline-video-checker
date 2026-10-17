# A09 - Rule sweep on A02's VLM states

- **Date:** 2026-10-17
- **Status:** measured; no gain on lockbox
- **Where it ran:** laptop, re-scoring A02's saved states; harness `reasearch1/validation-evidence/harness/arch_rule_sweep.py`

## Approach

Keep only rules that fire more on violation than clean dev clips, tune their thresholds on
dev, then score the lockbox once.

## Results

| Config | Dev (24) | Lockbox (16) |
|---|---|---|
| Kit defaults, all rules (all 40) | recall 19/21, clean FP 16/19, 22/40 | |
| Defaults + keep-list | 15/24 | 8/16 (recall 6/9, clean FP 5/7) |
| Tuned + keep-list | 16/24 | 8/16 (recall 6/9, clean FP 5/7) |

Keep-list chosen on dev: client_left_count, door_open, leave_cash, leave_docs, no_id.

## Logs

- `reasearch1/validation-evidence/logs/arch_rule_sweep.txt`

## Conclusion

Tuning helps on dev and disappears on lockbox: the false alarms come from perception, not thresholds.
