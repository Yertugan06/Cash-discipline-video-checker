# A22 CV experiments and decisions

Base: `5fae84b`. Live service remains A21: **30/40 organizer agreement,0clean false alarms**. No A22 production improvement is claimed. All40 public clips influenced development; these results are not held-out accuracy.

The append-only event ledger is [experiments.jsonl](experiments.jsonl). [Human clarifications](human-clarifications.json) are evaluation observations, not model inputs or runtime exceptions. Exact prompts, revisions, commands, source/input hashes, raw numeric results and worker reports are being collected beside this log. Pixels and credentials are excluded.

| ID | Attempt | Measured result | Decision |
|---|---|---|---|
|001|Backward cash tracking|4new samples across40clips; no finding or handover changes; X4history still too short|Do not promote|
|002|Use actual wrists globally|Lost X34's existing supported finding|Reject|
|003|Fixture/pose evidence|680safe-proximity samples;400lack exact reliable wrist support; projection remains ambiguous|Diagnostic candidate only|
|004|OWLv2-large,1008input|4/7cash positives,0/4false positives;1/1IDpositive and1/1IDnegative false positive|No cash advantage; no substitution|
|005|GroundingDINO combined captions|Ambiguous labels produced unknowns|Invalid adapter measurement; not model accuracy|
|006|GroundingDINO independent captions|7/7cash positives but4/4cash negatives falsely detected|Reject|
|007|Native128cash/ID proposals|Paired cash recall4/7→5/7; user then confirms new false cash inX40|Reject raw variant|
|008|LLM CV-context serializer|4focused tests;1,465B actual prompt context; no new inference result|Candidate only|
|009|8Btemporal laptop/safe action|Pilots completed; laptop errors and insufficient safe-action duration|Do not promote|
|010|Production promotion|No A22candidate passes yet|Keep working service unchanged|
|013|4Btemporal laptop comparison|Nine windows; X22/X23/X29 locked controls predicted working|Reject laptop promotion|
|014|8Btarget semantics|24/24unknown, including3decode/time errors|No semantic-filter benefit; do not promote|

## Comparison correction

The first OWLv2-large update compared4cash positives with the historical A21probe's5. That historical probe recalibrated the desk; the new paired probe uses the canonical cached desk and its baseline catches4. The comparison is therefore **no established cash gain**, rather than a proven4-versus5regression. The paired native128gain is4→5, not5→6. Larger-model ID labels are sparse. Every comparison records its actual crop/calibration policy.

## Human evidence added during this iteration

- X11: laptop left on/unlocked; other equipment on; turns lights off and departs approximately18s. Broad workspace neglect is an interpretation; specific rule conditions still need visual evidence.
- X12: user explicitly confirms laptop locked and lid closed, equipment shut down, key taken and lights off. A dark screen alone does not prove shutdown.
- X40at18s: no cash, only coat and personal handbag. This exposes a false cash proposal and blocks promotion of the raw crop variant.

## Original next decision, before the completed pilots

Run the prepared short temporal pilots, preserve unknowns, and inspect actual neural boxes/actions before changing a rule or the live service. A promising change receives focused controls and then an all40replay. Rejected experiments remain logged rather than becoming hidden fallbacks.

## Current status after A23–A25

A23 tested fresh main `4a3b9ea` on three synthetic and eight actual mirrored files.
All are visible on :8103; [A23 results](../A23-transfer-eval/README.md) distinguish
binary agreement from supported reasons. Synthetic accuracy is unscored; mirror
agreement is5/8 with an unsupported outsider reason for the sole positive.

Our own cash-presence head was actually trained in A24, then improved on its
training fit with train-only model selection in A25. The four probe decisions did
not improve (one cash detection, three unknowns). Neither classifier is promoted.
See [A24](../A24-own-cash-model/REPORT.md) and [A25](../A25-cash-head/REPORT.md).
These are region classifiers, not trained bounding-box detectors or rule evidence.

Detailed per-frame proposal/pose traces stay local and are excluded from Git.
`PRIVATE_ARTIFACTS.json` records their hashes; committed summaries, protocols and
source retain the experiment decisions without adding the raw trace corpus.

## 04:49 UTC pilot results

- **011 — 8B laptop:** X11working and X12closed match the human observations in sampled frames. Four windows return one state for four images and remain unknown; raw X22working conflicts with the described lock. Three X11departure candidates also need validation. Hold promotion.
- **012 — 8B safe action:** X20at7/7.5/8s shows table/counter work with the safe open in all three answers. Five controls have no valid CV trigger, and this covers only1s. Keep as a useful observed relation; it does not establish a >3s unattended interval or an end-to-end accuracy gain.
