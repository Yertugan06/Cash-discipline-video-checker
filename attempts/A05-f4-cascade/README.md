# A05 - F4: proposer + VLM verifier cascade

- **Date:** 2026-10-17
- **Status:** measured, rejected
- **Where it ran:** laptop RTX 4080; harness `validation/validation-evidence/harness/f4_cascade.py`, `motion.py`
- **Models:** Qwen3-VL-4B-Instruct as verifier

## Approach

A cheap proposer picks the top 5 windows (motion peaks, or uniform), then the VLM checks each window.

## Results (40 videos)

| Config | TP/FN/FP/TN | Correct | Dev / lockbox | Top-1 ±2 s / ±3 s | Worst runtime |
|---|---|---|---|---|---|
| motion top-5 | 8/13/7/12 | 20 | 12/24, 8/16 | 0 / 1 | 44.1 s |
| uniform top-5 | 10/11/9/10 | 20 | 11/24, 9/16 | 1 / 1 | 41.4 s |

Proposer recall (`validation/validation-evidence/logs/proposer_recall.txt`): motion keeps 20/22 events at about 72% coverage,
uniform 19/22 at 86%.

## Logs

- `validation/validation-evidence/logs/F4_motion_short_K5.txt`, `F4_uniform10_K5.txt`, `score_F4.txt`, `score_F4_uniform.txt`, `proposer_recall.txt`, `motion.txt`

## Conclusion

Same result with motion or uniform windows: the verifier is the bottleneck (see A08).
