# Peer detector: promising training approach, no transferable public checkpoint

Review at 2026-10-18 05:05–05:09 UTC, against our shared/a23/base main4a3b9ea. Peer checkout pin verified: `15d60a51fc5eebd6b91fff2b43866dd75dff13d7`. Only this attempt directory changed. No peer modules/scripts imported or executed; no pixel decoding, GPU, dependency install, downloads of weights or production mutation.

## Immediate decision

**Do not schedule a peer GPU run: fine-tuned weights are unavailable in the checked public locations.** Local `models/` contains only README.md; no model binary, fine-tuned config, annotation export or dataset split manifest is present. The [pinned setup section](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/README.md#L294-L297) says the fine-tuned archive accompanies their submission; it provides no archive/download URL.

Actual metadata calls succeeded: [GitHub releases](https://api.github.com/repos/Hotel-zulu/ForteDatathon/releases?per_page=100) and tags are empty; license endpoint404. HF model search `rtdetr_cashier` and author `Hotel-zulu` returned empty lists. Responses are saved in public-metadata.json. This does not rule out a private or undisclosed archive; it establishes that no usable public download was found. There is no honest pinned peer download command to provide.

## What the primary artifacts actually establish

| Question | Checked result |
| --- | --- |
| Detector | `RTDetrV2ForObjectDetection`, base PekingU/rtdetr_v2_r18vd; separate COCO person model and greedy IoU tracker |
| Custom checkpoint location | Local `models/rtdetr_cashier`, overridable by RTDETR_WEIGHTS; no published custom URL |
| Format | Training calls HF `save_pretrained(OUT)`; intended HF directory. Actual custom file format/hash/config unavailable; do not assume a safe binary exists |
| Classes | Builder has17 ordered classes; IDs0 cash,1 id_card,12 key_in_lock,14 screen_on,15 screen_locked,16 cash_in_counter. Complete intended map in static-audit.json |
| Data count | README stage4 claims1428 train+val frames; architecture says1386 and builder adds zone frames, which could explain the42-frame difference. CSV records77epochs, not dataset contents. Actual frame/box counts remain unverified |
| Split code | Builder assigns all records of each data.video identifier to one split; default random20%, seed0; explicit --val supported |
| Reported split | README specifies X3/X10/X33/X39. Export/split manifest absent, so actual training split cannot be checked |
| Leakage | --all concatenates train+val; README explicitly says final stage does so. Video-ID split also lacks content-hash duplicate grouping |
| Aggregate mAP artifact | CSV has77rows; stage-end mAP50 .749/.782/.841/.851. Stage4 includes validation data in training |
| Per-class mAP | Money .83, ID .93, key .94 at stage3 and final money .86/ID .93/key .92 are README claims. No per-class result artifact/config to verify them |
| 35/42 verdicts | README reports20/20 clean and15/22 violations. No raw final API results/timelines/checkpoint provided, so not reproduced. Rules explicitly say thresholds were tuned on all42 public clips |
| VLM | Registry returns None for verifier; this is detector/pixel/temporal-rule output, not a verified second-stage local LLM |

Sources: pinned [dataset builder](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/scripts/build_dataset.py#L23-L26), [split implementation](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/scripts/build_dataset.py#L46-L64), [training](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/scripts/train_rtdetr.py#L165-L177), [CSV](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/docs/training_metrics.csv), [metrics claims](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/README.md#L219-L277).

## Inference compatibility if the archive becomes available

The [actual inference code](https://github.com/Hotel-zulu/ForteDatathon/blob/15d60a51fc5eebd6b91fff2b43866dd75dff13d7/src/detectors/rtdetr_perception.py#L54-L109) uses RGB, float NCHW /255, bilinear antialiased square resize, no mean/std normalization. Service default is640square, training default800square. Forward input is pixel_values; outputs are sigmoid(logits) and normalized cxcywh boxes, top100 flattened query/class scores, threshold .3, then per-class IoU NMS .6. Person threshold is .35. Avoid blindly applying an unrelated processor or adding normalization.

The actual [base config/preprocessor](https://huggingface.co/PekingU/rtdetr_v2_r18vd/tree/5650961749fa93567c0d46fc7f43ea4f9e914107) confirms COCO80, model_type rt_detr_v2, no normalization, RGB rescale1/255 and640square defaults. **It has none of cash/id_card/key_in_lock/screen_locked.** Available file is model.safetensors, approximately80.9MB. Base revision5650961749fa93567c0d46fc7f43ea4f9e914107 and [base model card](https://huggingface.co/PekingU/rtdetr_v2_r18vd/blob/5650961749fa93567c0d46fc7f43ea4f9e914107/README.md) declare Apache-2.0. Safe base download locations, useful only for a future training pilot:

```text
https://huggingface.co/PekingU/rtdetr_v2_r18vd/resolve/5650961749fa93567c0d46fc7f43ea4f9e914107/model.safetensors
https://huggingface.co/PekingU/rtdetr_v2_r18vd/resolve/5650961749fa93567c0d46fc7f43ea4f9e914107/config.json
https://huggingface.co/PekingU/rtdetr_v2_r18vd/resolve/5650961749fa93567c0d46fc7f43ea4f9e914107/preprocessor_config.json
```

Pin and inspect any supplied custom config/class map, safetensors hashes and license before scheduling the parent GPU job. Use installed official Transformers with local_files_only=True and use_safetensors=True; no pickle or trust_remote_code. Class detection supplies boxes/presence only: no cash owner, session identity, lock mechanism or violation is inferred.

## License and logic findings

No LICENSE/COPYING/NOTICE is tracked at the pin; GitHub license endpoint returns404. README labels the derivative model Apache-2.0, but this is neither an available weight artifact/license package nor a general repository code grant. Do not copy peer code verbatim. Learning the small-object training approach remains possible; no peer code was copied into our source.

No runtime filename-to-verdict, annotation lookup or per-clip timestamp branch was found in the reviewed active inference path. Clip IDs in comments/docstrings and regulations' videos lists are evaluation context; the active loader reads legal templates/enabled flags, while eval_timelines.py uses those videos lists for evaluation. Do not confuse this with independent validation.

The active rules still contain assumptions unsuitable for transfer: sparse ID detections become non-presentation; any cash at next client is called previous-session cash; three people plus ID becomes third-party presentation; safe-open duration/cutoff becomes 'cashier busy elsewhere'; brightness can stand in for unlocked state; track paths are reconstructed across misses by nearest boxes. Fixed candidate confidences (.5/.6/.7 etc.) are heuristic scores, not calibrated probabilities. Legal links/quotes/descriptions are fixed YAML templates; they are not established by detector accuracy and were not legally audited here.

Missing weights can also fall back to NullPerception in the peer registry, allowing an empty observation stream and clean verdict. A new pilot must fail explicitly instead of adopting this behavior.

## Frozen A13 baseline and smallest conditional pilot

Actual numeric rescoring of our existing A13 logs, not a fresh main4a3 inference run:

| Model | Cash TP/FN/TN/FP, Npositive7/Nnegative4 | ID TP/FN/TN/FP, Npositive1/Nnegative1 |
| --- | --- | --- |
| OWLv2 base | 0/7/4/0 | 1/0/0/1 |
| Grounding DINO base | 1/6/3/1 | 0/1/0/1 |
| Qwen2.5-VL-7B | 0/7/4/0 | 0/1/0/1 |

Unknown counts0 for these saved records. Historical4/11 is cash presence accuracy, not recall. A13 has frame-presence labels, **no object-box gold**, so this pilot cannot produce mAP or box IoU accuracy. ID has only two labeled frames. All public clips influenced development; no held-out claim.

`frozen-20-frame-plan.json` freezes the existing20 A13 targets and thresholds before any transfer inference. If a verified custom archive arrives, parent can use one serialized GPU job to run those20 local RGB frames at640, then a controlled800square comparison (40 forward passes). Preserve native sizes, frame/model/config hashes, timing and class/score/normalized boxes. Keep images on VM; export only allowlisted numeric/text results. Gold/clip/time are evaluation selectors only and never model features. Missing model/invalid output stays unknown. No legal or tracking hook is proposed.

**Smallest own training route:** cash-only first, with human-reviewed boxes plus hard negative crops; ID/key/lock stay out until adequately labeled. A13 presence labels cannot train a box head. A small authorized box set must first be created locally, split by source-video content hash (including duplicates), with the frozen A13 targets excluded from training. Reuse official installed Transformers and a pinned Apache base; a short head/backbone fine-tune is a feasibility pilot, not a replacement model claim. No labeled1428-frame set is available from this peer, and no training runtime/quality improvement can be promised in the remaining approximately55minutes. If boxes are not already available, a reviewed small-object pilot is more feasible than claiming a validated fine-tuned replacement before06:05. Current main already has a calibrated desk-crop OWLv2 pass; adding the same crop again is not a new approach. No training code or backend framework was added for unavailable data/weights.

## Validation and runnable artifact

`audit.py` is standard-library-only. It verifies the exact peer git pin, reads AST literals without executing peer source, counts CSV rows, rescored saved A13 records and writes the20frame evaluation fixture. Confusion-count and unknown-is-not-negative self-checks passed. Ruff initially found formatting/line-length issues; corrected, then checked again. `public-metadata.json` records actual successful JSON/text metadata reads; it contains no dataset pixels.

Exact CPU argv is in cpu-command.json. From this worktree:

```bash
.venv/bin/python attempts/A23-transfer-eval/peer-detector/audit.py --peer /home/ubuntu/workspaces/datathon26-workers/shared/a23-peers/hotel --a13 attempts/A13-detection-spike --out attempts/A23-transfer-eval/peer-detector
```

Skipped: training, peer execution, actual new video inference, GPU and broad test suites. Blocking risks: absent custom weights/config/license, unverified labels/splits/results, and unresolved ownership/visibility even if object recall improves.
