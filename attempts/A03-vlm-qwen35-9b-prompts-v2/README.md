# A03 - Qwen3.5-9B questionnaire, prompts v2

- **Date:** 2026-10-17
- **Status:** gold frames measured; full run stopped after 5 videos, no full score
- **Where it ran:** `datathon` (L4), `~/forte_brev_kit/brev_kit`, runs `qwen_qwen3_5-9b_prompts_v2_1024_gold` and `qwen_qwen3_5-9b_prompts_v2_1024`
- **Models:** as A02, max side 1024 px, `prompts_v2`; zoom variant re-asks on crops

## Approach

Same pipeline as A02 with rewritten prompts, larger frames and an optional zoomed re-ask.

## Results

| Gold-frame checks (56) | Correct |
|---|---|
| A02 baseline | 44 (79%) |
| prompts v2, 1024 px | 50 (89%) |
| prompts v2 + zoom | 51 (91%) |

Still weak: `key_in_safe_lock` (0/2, 1/2 with zoom), `room_door` 1/2, `cashier_action` 2/3.
The full-video run produced states for 5 videos only; no video-level score exists.

## Logs

- `logs/report_states.md`, `logs/report_states_zoom.md` - gold reports with errors
- `logs/run_meta.json`, `logs/v2_all.log`
- Partial full-run states: `datathon:~/forte_brev_kit/brev_kit/runs/qwen_qwen3_5-9b_prompts_v2_1024/states/`

## Conclusion

Better per-frame perception on gold frames, but unproven at video level. Worth finishing the
full run only if the VLM path is still in play (see A12 detector decision).
