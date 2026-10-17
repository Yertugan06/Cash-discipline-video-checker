# A07 - F2: frozen embeddings + linear probe

- **Date:** 2026-10-17, after Addendum B of the pre-registration
- **Status:** measured, rejected
- **Where it ran:** `datathon2` (L4); harness `reasearch1/validation-evidence/harness/f2_probe.py`
- **Models:** DINOv2-base (rev `f9e44c81`), SigLIP2-base-patch16-384 (rev `f775b65a`)

## Approach

Frame features at 2 fps from two crops, centred per clip, averaged over ±2 s windows.
Logistic regression trained leave-one-group-out over the 22 groups (clean twins held out together).

## Results (40 videos)

| Encoder | TP/FN/FP/TN | Correct | Dev / lockbox |
|---|---|---|---|
| DINOv2, centred | 17/4/15/4 | 21 | 14/24, 7/16 |
| DINOv2, raw | 16/5/17/2 | 18 | 12/24, 6/16 |
| SigLIP2, centred | 12/9/10/9 | 21 | 13/24, 8/16 |
| SigLIP2, raw | 5/16/3/16 | 21 | 14/24, 7/16 |

Video AUC 0.49-0.54 for all four, below the duration shortcut (0.68). Window AUC vs clean
twins 0.49-0.67. Best localization (DINOv2 centred, ±3 s 11/22) ties the blind prior (12/22).
Pre-registered bar (AUC >= 0.70 and beat the prior): not met.

## Logs

- `reasearch1/validation-evidence/logs/datathon2/F2_*.txt`, `score_F2_*.txt`

## Conclusion

40 clips don't carry a learnable signal for generic image features.
