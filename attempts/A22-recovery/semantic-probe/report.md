COMPLETED — no semantic filter benefit; not promoted.

Parent execution returned24unknown answers from24queries, including3decode/time
mismatches. Cold load96.64s, total113.67s. Actual numeric/text results are in
results/. The following preserves the original prepared protocol; its pending
status is historical.

GPU_RUN_READY

Prepared a target semantics pilot without production edits or GPU execution. Exact argv: `argv-datathon3.json`; frozen24queries/prompt/model/settings: `preregistration.json`. Run only after the current safe probe releases the GPU; the runner holds `~/.cache/datathon-workers/gpu.lock` itself, so do not wrap another flock around it. Output `/tmp/a22-target-semantics-01` must not already exist. Existing local environment and offline Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, bf16/SDPA, are reused. No downloads/dependency changes.

Selection is numeric-only and outcome-independent: successful finite cash/bundle/ID NN boxes with both source dimensions <=128px; ranked by actual NN score, then call index and geometry. Within each frame interleave OWLv2/DINO ranks and suppress IoU>=0.5 duplicate geometry regardless of NN label. Round robin all twenty fixed input frames, at most24queries. Twenty frames are covered, including all seven cash-positive frames, five cash-negative frames (the new human-confirmed X40 negative included), and the sparse one positive/one negative ID label. Ten first-round targets come from OWLv2, ten from DINO, and four additional targets from DINO. The genuine OWL X40 bundle proposal is included by the same policy used for every frame. No human box or outcome controls the policy.

Every request uses an identical fixed prompt and two images: full original frame annotated with the exact actual NN box and its128px native context annotated with the same box. No source NN class, score, label, clip name, time, rule or user text reaches the model. The processor's existing size API caps each image at1048576pixels and sets a65536pixel minimum; the native128crop is thus upsampled by the processor, explicitly recorded via image_grid_thw. No image file is written. Only local in-memory decode/overlay runs on the orchestrator VM. Results preserve video SHA, NN model/crop/call provenance, source inference/seed times, decoded time, original RGB/crop/annotated-view SHA256 hashes and neural box. Only clear banknotes/id_card answers return that unchanged neural detection and box, with owner/track cleared. Its original NN label/score remain unchanged; the separate answer is the semantic class and is not a calibrated score. All other categories are explicit rejections; unknown/model/parser/decode/deadline failure remains unknown. No ownership, handover, motion or interval absence is inferred.

The raw native128 ROI candidate is rejected because human review confirmed X40 had no cash. This semantic pilot is an independent diagnostic, not a production promotion. Evaluation labels including that fact are isolated in evaluation-labels.json, which pilot.py never reads. evaluate.py reports proposal retention and rejection, not absence or target-box accuracy. To score after the GPU run:

```bash
/home/ubuntu/workspaces/datathon26-workers/shared/a21/visual-venv/bin/python /home/ubuntu/workspaces/datathon26-workers/worker-1/attempts/A22-recovery/semantic-probe/evaluate.py /tmp/a22-target-semantics-01/results.json
```

Actual focused CPU check: `.venv/bin/python attempts/A22-recovery/semantic-probe/check.py` -> `strict parser checks passed` and `24 genuine proposals across20frames; labels do not affect selection; X40target included`. This asserts source-box provenance for every selected proposal, selection invariance when all expected labels are replaced, bounded query count, complete frame coverage and strict JSON parsing (duplicate/extra keys, unsupported labels and markdown are rejected). `pilot.py --help` exits0. Ruff passes for the three scripts after fixing import ordering/string line lengths. No broad suite, model inference, dataset decode or processor image check was run here.

Runtime bounds: at most24generations,32new tokens each, greedy, max_time15s/call,240s including model load after imports. Timeouts are cooperative around an in-flight CUDA forward; no hard preemption claim. The protocol/schema and model manifest are checked before execution. Metadata includes script/registration/model-manifest hashes, latency, image grids and peak allocated GPU memory. Outputs remain numeric/text only.

Primary API check used Context7 Transformers v5.19.0 Qwen3VL documentation and the current base's existing offline Qwen load/template/generate path (installed Transformers5.20.1). The shared worker accepts only a single crop, so this standalone pilot reuses its minimal load/generation sequence for the required two views; no alternative inference framework was added.

Limits: source proposals have no box gold, one still cannot prove interval absence, unknowns are not clean negatives, source-model raw tensor finiteness cannot be certified retrospectively, and the same object may have ambiguous NN class labels. The24query cap leaves some alternate proposals unverified. All40publicclips influenced development; no held-out accuracy claim. GPU answers/latency and the semantic acceptance gate are unmeasured until parent execution and review. No integration patch is justified yet.
