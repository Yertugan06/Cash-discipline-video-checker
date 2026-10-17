# A02 - VLM per-frame questionnaire (Qwen3.5-9B)

- **Date:** 2026-10-17, finished 13:11 UTC
- **Status:** measured
- **Where it ran:** `datathon` (L4), `~/forte_brev_kit/brev_kit`, run `q35_9b_fp8` (full) and `q35_9b_fp8_gold` (gold frames)
- **Models:** Qwen/Qwen3.5-9B, FP8 online quantization, vLLM 0.31.0, 16k context, thinking off, JSON-schema output

## Approach

Sample 1 frame per second (max side 768 px). The VLM fills a fixed questionnaire per frame
(cashier at desk, cash on desk, safe door, laptop screen, ...). `timeline_rules.py` turns the
state timeline into violations.

## Results

Gold frames (56 hand-labelled field checks): **44/56 (79%)**. Weakest fields:
`key_in_safe_lock` 0/2, `desk_cash` 1/3, `room_door` 1/2, `clients_at_desk` 2/4.

Full run (40 unique videos):

| Metric | Value |
|---|---|
| Correct verdicts /40 | 22 (55%) |
| Recall | 19/21 (90%) |
| Clean false alarms | 16/19 (84%) |
| Timecode ±1 / ±3 / ±5 s | 8 / 13 / 16 of 22 |
| Norm id matched | 6/13 |
| Extra events | 112 |
| Mean / worst VLM time | 83.6 s / **344.2 s (X-14, over the 300 s limit)** |
| Schema failures | 0 of 1314 answers |

## Logs

- `logs/report_videos.md` - full-run report with the per-label table
- `logs/report_gold_states.md` - gold-frame report with errors
- `logs/run_meta.json` - per-video frames and latency
- `logs/violations/` - per-video violation events
- Raw per-frame states: `datathon:~/forte_brev_kit/brev_kit/runs/q35_9b_fp8/states/`

## Conclusion

Good recall and timecodes, but it flags almost every clean video, and 1 s sampling breaks the
time limit on long clips. The rule sweep on these states (A09) didn't fix the false alarms.
