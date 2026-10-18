# Limitations and known error cases

Current implementation: A21, F1 plus local Qwen3-VL-4B safe-state checks, running on
one datathon2 VM. Exact results and provenance: [A21 release](../attempts/A21-deadline/RESULTS.md).
The public endpoint on datathon was last recorded with A20 and was not upgraded by A21.

## Measured detection quality

| Run | Correct unique verdicts | Violations caught / missed | Clean false alarms |
|---|---|---|---|
| Historical A20 | 32/40 | 13 / 8 | 0/19 |
| Current A21, VLM enabled | 30/40 | 11 / 10 | 0/19 |

The two lost catches were X4/X47 and X20. Their A20 verdicts agreed with labels, but
ID-before-cash and documents-on-exit explanations contradicted the supplied observations.
A21 removes those accusations without recovering the actual violations. Supported findings
remain 9; 3 findings have unknown observation support. No overall detection improvement or
complete explanation accuracy is claimed. The VLM has not improved the verdict score.

All 40 public clips influenced development. These results are not held-out accuracy or
proof of performance on a new room, camera, layout or scenario. X4/X47 and X5/X48 are byte
duplicates; 42 file results represent 40 independent video hashes.

## Current misses and uncertainty

| Clip/group | Observation or capability gap |
|---|---|
| X1, X2 | Organizer labels are retained, but the causes remain unresolved. Hand counting, counterfeit money or a blanket ID-first requirement are not established by these notes. |
| X4/X47 | Earlier cash remains at the next client's entry; later cash is stacked. Recognition/provenance does not support the correct finding. Cash first detected during a new session can be attributed incorrectly. |
| X11 | Human prose supports leaving; reliable working-versus-locked screen evidence is missing. X11/X12 supplied descriptions are identical, so prose alone does not establish their screen difference. |
| X13 | Bundles from an opened bag reach the safe without a described recount; cash/bundle transfer evidence is missing. |
| X20 | Safe is left open while work continues. Safe-open answers exist, but image-plane proximity marks the cashier as attending it for too long. |
| X22 | Key-after-exit capability is disabled/unimplemented; a shut door does not prove locking or key removal. |
| X32, X33 | Door state remains unreliable. The local verifier also answered open on clean X31; door answers stay diagnostic-only. |
| X44 | Rejected-note recombination without detector inspection is not implemented. It is distinct from returning a questionable note to a client. |

Missing detections are not proof of absence. `C-ID-BEFORE-CASH` requires an explicit,
attributed continuously observed non-presentation interval; no production producer currently
provides it. A still-frame unknown/no-ID answer cannot provide that interval. Policy scope
and legal applicability remain unverified.

The default-false `desk_objects` experiment remains available for isolated comparisons;
A18/A19 did not improve accuracy and it is not enabled in the deployed service.

## Sampling, tracking and state verification

F1 samples the whole clip at 2 fps. Processing every sample (`coverage.mode="full"`) does
not mean every object/action was recognized. Brief actions, occlusion, track fragmentation,
pose estimates and wrong fixture calibration can corrupt ownership or attendance evidence.
Raw states normally use hysteresis; verified categorical answers update only their exact
sampled frames. Unknowns and gaps do not establish absence or continuous duration. A
recording cutoff does not establish a future abandoned object; X43/X45 remain clear.

Only the safe family is enabled for the local VLM. It does not detect cash/ID objects or
produce legal conclusions. Door checks are diagnostic; laptop checks are not enabled.

The fixed 12-input Qwen crop/temporal probe left most cash cases unknown and produced a
false ID answer in the temporal variant. Sparse labels lack box/track ground truth. In the
older A13 re-score, OWLv2 and Qwen2.5-VL-7B each detected **0/7 cash positives**; their
4/11 cash accuracy came from four true negatives, not four successful cash detections.
See [the numeric re-score](../attempts/A20-night-orchestration/logs/a13-small-object-rescore.json).

## Runtime, queue and cache limits

- One FIFO worker processes one GPU video job at a time. The gateway submits serially.
  Under a burst of uploads each job gets a fair share of its time and may be sampled at
  1 or 0.5 fps instead of 2 (reported in `warnings`); accuracy at those rates is not
  measured. Simulated with the measured L4 cost (0.55 s/frame, VLM off), five 142 s
  uploads at once all finish at 0.5 fps in about 240 s; if the real cost is 45% higher
  they are all cut off. A cut-off job without findings fails ("Analysis incomplete")
  and counts as unprocessed. No real burst has been run on the L4.
- The enabled 42-file pass reused perception for 41 files and 476 previous VLM answers;
  40 VLM calls ran afresh. Its median 2.0675 s is predominantly cached work.
- Forced-cold X20: 50.669 s, 23/23 samples, 23 fresh VLM calls, no errors/deadline hit.
- The longest clip (142.533 s) completed cold in 158.6 s with the VLM **off**. Cold longest-
  clip latency with the current enabled configuration has not been measured.
- Cached perception is keyed by source/config/model identity. The compatibility-only flag
  restoration reused identical numeric payloads after AST/config comparison; its copy is
  explicit and recorded, not claimed as new neural inference.

## Camera and generalization

The user confirms one fixed physical camera position with several table/equipment setups
and scenario groups. References to a previous clip supply setup context, not established
cross-file transaction continuity. Zones and desk-relative distances are calibrated per clip;
this reduces hardcoded layout assumptions but does not prove unseen-angle performance.
Historical A20 mirror/zoom/drop replays perturb cached geometry; they are not new filmed data
or a measured robustness result for every A21 change.

## Legal grounding

All 12 citations in the current API run remain `pending`. Human source verification is
required before marking a norm/act verified. Current operation uses `RULE_SCOPE=detector`;
`jury` scope has no eligible rules and refuses startup. Neither matching an organizer
verdict nor proximity to its timestamp verifies a rule, legal clause or causal explanation.
See [the Knowledge Pack](../knowledge/README.md) for unresolved source conflicts.

## Data handling

Checker uploads and sampled frames are removed after jobs; stored API results/evidence
follow the configured TTL. The review gateway retains source folder videos, persistent
annotations, drafts and saved runs separately. Upload replay files can remain until the
gateway restarts. TTL is not a promise to delete every annotation/cache at that moment.
Hackathon dataset use/deletion still follows the organizer's restrictions.

No dataset media is sent to cloud AI. There is no face-identity database or audio analysis.
Outputs are signs for human review, not disciplinary/legal conclusions. At most three
findings are returned, so lower-ranked findings can be omitted.
