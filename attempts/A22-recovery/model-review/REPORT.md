# Independent model-adapter review

2026-10-18, D3-2. Reviewed all 20 records in each of the three actual pilots (60 records, 457 exported boxes). **No new adapter/postprocessing bug found that rescues either model substitution. No patch proposed. Keep both out of the live service.**

| Run | Cash TP / FN / TN / FP | ID TP / FN / TN / FP | Failed crop calls |
|---|---|---|---:|
| OWLv2-large1008 | 4 / 3 / 4 / 0 | 1 / 0 / 0 / 1 | 0 |
| DINO-01 merged-caption parser | all 11 labeled cash cases unknown | both labeled ID cases unknown | 40 |
| DINO-02 independent captions | 7 / 0 / 0 / 4 | 1 / 0 / 0 / 1 | 0 |

These are development frame-presence labels, not boxes or held-out accuracy. Unlabeled classes/frames remain unscored; DINO non-cash/ID classes are correctly unknown. Full and full+desk have the same labeled cash/ID counts. Existing OWLv2 base full+desk is 5/7 cash TP with 4 TN per the supplied comparison, so large is not a useful replacement.

## Adapter/API/numerical checks

- Current DINO code queries banknotes and identity card independently, keeps actual text-label membership, and maps each result to the queried class. It does not assign class from annotations, filename or a desired answer. Repeated cash/ID geometry is semantic ambiguity, not proof of either physical class.
- Installed local Transformers source is 5.20.1. Its DINO processor computes sigmoid(logits), then max over tokens for the detection score; text_threshold selects label tokens. No single-class softmax-to-one bug exists here. OWLv2 also takes max-logit sigmoid rather than normalizing one class to probability one. These are model-specific semantic scores, not calibrated probabilities of real-world presence; thresholds across these models are not directly comparable.
- Negative infinity in DINO padded logits is allowed (sigmoid -> 0). The corrected adapter rejects NaN/+infinity logits and nonfinite boxes. DINO-01 invalid counters can include normal -infinity padding alongside merged-label parser failures; raw logits were not retained, so numerical corruption is not established. Its unknown outputs are adapter failures, not model accuracy. Do not treat its large invalid counters as proof of corrupted numerical inference.
- All 457 exported box/score tuples are finite, score within [0,1], normalized coordinates ordered and within [0,1]. All logged confusion summaries were independently recomputed from all 60 records and matched. All three runs use the same 20 input cases/sizes/expected-label dictionaries. DINO-02 registered runner hash matches the current adapter.
- target_sizes=(height,width), pixel-to-normalized conversion, crop-local-to-frame remapping and class-aware NMS match the existing helpers. DINO max-longest-edge 1333 explains actual 1333x729 / 631x1333 tensors despite the registration shorthand 800 shortest side; this is not a width/height swap. OWL tensors are 1008x1008. Model and input resolution changed together.
- Offline environment variables and local_files_only=True are present; images are decoded locally. Manifests identify pinned large-OWL and DINO-base repositories/revisions. No remote vision/model call or score/label injection is visible. The reviewed script does not itself take the GPU flock: root must retain the external one-job-per-VM lock.

## Numeric geometry evidence

- OWL cash boxes: 0.0445–0.1465% of frame area (12 detections across full/desk calls). ID boxes: 0.0278–0.1994% (30 detections). Largest cash/ID IoU against cached desk is 0.014 and against nearest-sampled person boxes is 0.012. These are small localized regions, not whole desks/people; class correctness remains unproven.
- DINO cash boxes: 0.0492–10.3646% of frame, median 0.1417% (53 detections). ID: 0.0225–1.2275%, median 0.0748% (83 detections). Largest person IoU is 0.112 cash / 0.097 ID; numbers do not support a general whole-person-box explanation.
- One conspicuously broad desk-crop cash box occupies 72.1% of cached desk area, desk IoU0.6825 and 66.8% of crop, touching its edge. This is a desk-extent/boundary artifact candidate from geometry alone, even on a frame labeled cash-positive; frame TP does not validate localization.
- Only 2/53 DINO cash and 3/83 ID call-level boxes touch a crop boundary within one source pixel. None of the eight cash boxes on the four real cash-negative frames touches a crop boundary. Their frame areas are only 0.1094–0.7765%, so removing whole-desk or edge boxes would not explain away the four negative-frame false positives. No such filter is proposed.
- DINO union outputs have 23 cash–ID box pairs with IoU>0.8, versus 6 for OWL. This is overlapping semantic assignment across independent queries; no mutually exclusive class resolution is supplied by label-wise NMS. It is a quality limitation, not evidence that relabeling either class is correct.
- Cash scores overlap: labeled-positive DINO boxes0.26305–0.57120; negative boxes0.28036–0.48908. ID-negative boxes reach0.56158, above the labeled-positive maximum0.49138. Do not choose a threshold on these outcomes or claim a calibrated class decision.

## Latency and next narrow step

Full+desk synchronized crop-call means are 0.432 s for large OWL and 1.415 s for corrected DINO; medians0.378/1.398 s, maxima1.428/2.325 s. DINO runs two independent captions per crop (four forwards per full+desk frame). Recorded complete-pilot wall times21.16/43.598 s include startup/decode overhead; they are not per-video service latency.

At2fps, a simple 180-second/360-frame extrapolation is about156 s large-OWL or509 s DINO for this object stage alone, before people/pose/state models or VLM checks. This is an extrapolation, not a measured full-video run; corrected DINO already conflicts with the300 s single-VM budget at that length. Recorded torch peak allocations are2.66/2.38 GB, not whole-process VRAM.

**Next: execute D3-1’s already prepared native128 paired pilot**, keeping the current base weights, prompts and0.12 threshold fixed. It changes source-crop scale rather than adding another model family. Keep all20 cases, including the four real cash negatives and the ID negative, explicit failures and actual per-variant GPU timings. Advance only on measured gains with preserved negatives; do not tune outcome-specific thresholds. Native128 is prepared, not yet shown useful by this review.

## Scope and limits

Requested shared/a22/base5fae is absent on this worker; the available shared/a22/base supplied the helpers reviewed. The result geometries are independently checkable from logged crop sizes/boxes; canonical base5fae byte identity is not established here. Old OWL/DINO-01 registrations do not pin runner hashes, so their exact historical implementation is not reconstructed; DINO-02 does pin and match.

All source/result hashes are in inputs.json; numeric-review.json retains per-box area/desk/person/crop statistics and actual call errors. Person overlap uses the nearest numeric-cache sample, not new video inference or box gold. Model manifests were read, but multi-GB weights were not rehashed. The registration does not retain the actual --weights argument or a loaded-weight digest, so manifest presence alone does not prove which bytes were loaded. No threshold changes, images, GPU, installs, production edits, full suite or new adapter code. No held-out/physical-class accuracy claim.

API reference: [official Grounding DINO documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino); installed processor source was the authority for the actual score/box calculations.
