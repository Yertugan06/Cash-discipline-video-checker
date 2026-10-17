# A08 - VLM window verifier vs matched clean twins

- **Date:** 2026-10-17 (Addendum A of the pre-registration)
- **Status:** measured; no discrimination
- **Where it ran:** laptop (4B) and `datathon2` L4 (4B reproduction, 8B); harness `validation/validation-evidence/harness/verify_windows.py`
- **Models:** Qwen3-VL-4B-Instruct, Qwen3-VL-8B-Instruct (bf16)

## Approach

8 s windows around each labelled event (4 fps, 448 px). Ask "is there a violation?" and
compare yes-rates with the same moment in the clean twin clip, random clean windows and
off-event windows.

## Results (yes-rate)

| Model / prompt | Labelled | Clean twin | Random clean | Off-event |
|---|---|---|---|---|
| 4B, checklist | 8/22 | 4/19 | 5/19 | 2/11 |
| 8B, checklist | 16/22 | 15/19 | 14/19 | 8/11 |
| 4B, per-item yes/no (dev) | 4/12 | 2/10 | 2/12 | 3/6 |
| 8B, per-item yes/no (dev) | 2/12 | 3/10 | 3/12 | 2/6 |

Peak VRAM 10.0 GB (4B), 18.4 GB (8B); 6-9 s per window.

## Logs

- `validation/validation-evidence/logs/datathon2/verify_q3vl4b_*.txt`, `verify_q3vl8b_*.txt`
- `validation/validation-evidence/logs/verify_4fps_s448.txt`, `vlm_profile_1.txt`

## Conclusion

Neither model separates real events from their clean twins; the 8B just says "yes" ~75% of
the time. Bigger zero-shot VLMs are not the fix.
