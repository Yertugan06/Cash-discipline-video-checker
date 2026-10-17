# A04 - F3: whole-video local VLM

- **Date:** 2026-10-17
- **Status:** measured, rejected
- **Where it ran:** laptop RTX 4080 12 GB (and reproduced on `datathon2` L4); harness `validation/validation-evidence/harness/f3_discovery.py`
- **Models:** Qwen3-VL-4B-Instruct (rev `ebb281ec`)

## Approach

Give the VLM the whole clip (1 fps, 288 px) or 30 s chunks (2 fps) and ask it to list
violations with timecodes. No proposals, no rules.

## Results (40 videos; dev 24 / lockbox 16)

| Config | TP/FN/FP/TN | Correct | Dev / lockbox | Top-1 ±2 s / ±3 s | Worst runtime |
|---|---|---|---|---|---|
| whole clip, 1 fps, 288 px | 8/13/4/15 | 23 | 15/24, 8/16 | 0 / 0 | 149.5 s |
| 30 s chunks, 2 fps | 9/12/8/11 | 20 | 12/24, 8/16 | 0 / 0 | 30.4 s |

## Logs

- `validation/validation-evidence/logs/F3_whole_1fps_s288.txt`, `F3_chunk30_2fps_s288.txt`
- `validation/validation-evidence/logs/score_F3_whole_1fps_s288.txt`, `score_F1_F3chunk.txt`, `score_by_split.txt`

## Conclusion

Best raw accuracy (23/40) but it misses most violations and never localizes them: the
pre-registered claim C2 is falsified. Not a discoverer.
