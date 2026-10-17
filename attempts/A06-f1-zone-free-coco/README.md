# A06 - F1 probe: COCO detector + zone-free rules

- **Date:** 2026-10-17
- **Status:** measured, rejected
- **Where it ran:** laptop, CPU; harness `validation/validation-evidence/harness/f1_rules.py`
- **Models:** RT-DETR v2 r18 (COCO, rev `56509617`)

## Approach

Generic COCO detections (person, phone, cup, bag ...) with simple temporal rules and no
scene zones. A quick check of whether generic CV separates the classes, not the full F1 app (A01).

## Results (40 videos)

| Metric | Value |
|---|---|
| TP/FN/FP/TN | 21/0/19/0 - flags every video |
| Correct | 21 (same as always "violation") |
| Top-1 ±2 s / ±3 s | 4 / 5 of 22 |
| Mechanism (17 reliable) | 2 |
| Worst runtime | 113 s on CPU |

## Logs

- `validation/validation-evidence/logs/F1_coco_rules.txt`, `score_F1_F3chunk.txt`

## Conclusion

Generic detections fire on every clip (claim C5 falsified). Zone-aware, mechanism-specific
perception (A01/A12) is the only F1 variant worth pursuing.
