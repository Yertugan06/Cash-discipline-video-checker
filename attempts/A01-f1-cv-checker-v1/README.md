# A01 - F1 CV checker v1 (forte-cash-checker snapshot)

- **Date:** 2026-10-17, run ~11:30-12:30 local
- **Status:** measured; superseded by A12 (same detector, ported into the ADR-002 service)
- **Where it ran:** `datathon` (L4), `~/forte-model-check-20261017-1114`, docker `forte-cash-checker:cuda`, `SAMPLE_FPS=5`
- **Models:** RT-DETR r18vd (people), OWLv2 base-patch16-ensemble (objects and scene, text prompts), CLIP ViT-B-32 laion2B (states), RTMPose-m wholebody ONNX (pose), ByteTrack (tracking)

## Approach

Detect people and objects per frame, track them, build events (left desk, cash on desk,
safe open, outsider in zone, ...) and evaluate 21 temporal rules from `codex.yaml`.
Every rule hit is a violation.

## Results (40 unique videos)

| Metric | Value |
|---|---|
| Correct verdicts /40 | 20 (50%) |
| Recall | 14/21 (67%) |
| Clean false alarms | 13/19 (68%) |
| Event recall ±1 / ±2 / ±5 s | 8 / 10 / 11 of 22 |
| Predicted events | 127 (117 false at ±2 s) |
| Mean / worst runtime | 83.9 s / 294.6 s (X-48/X-5), 0 over 300 s |
| Held-out 9 videos | 5/9 correct |

Worst false-alarm rules (`logs/per_rule.csv`): A-OUTSIDER-ZONE 71, A-SECOND-PERSON 31,
L-NO-DOCS-ON-LEAVE 13, W-NO-PERSONAL-ITEMS 4.

## Logs

- `logs/eval.log` - per-video run log and summary lines
- `logs/summary.json`, `summary.csv`, `per_video.csv`, `per_rule.csv`, `incremental_rules.csv`, `misses.json`, `pairs.csv`
- Full results with evidence (34 MB `results.json`, HTML report): `datathon:~/forte-model-check-20261017-1114/output/gpu/`

## Conclusion

Fast enough, but it flags too often: 6 of 21 rules produce almost all false alarms.
Turning off or tightening those rules is the cheapest improvement for A12.
