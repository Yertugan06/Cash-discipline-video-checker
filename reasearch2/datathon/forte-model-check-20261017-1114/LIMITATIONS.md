# v1 limitations and measured checks

The complete local pipeline and all 16 priority-1 rule functions are implemented.
**Detection quality is experimental and currently poor on the CPU validation clips.**
A completed run means the pipeline ran, not that its interpretation is correct.
Do not treat a clean result as proof of compliance when coverage warnings are present.

## Measured results

| Run | Clips | Sampling | Accuracy | Violation recall | False-alarm rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial paired CPU diagnostics, before geometry/crop fixes | 6 | 0.5 fps | 33.33% | 33.33% | 66.67% |
| Later cash-leaving pair X-26 / X-27, with hip/desk guards and desk crops | 2 | 0.5 fps | 50% | 0% | 0% |
| Full training set | 42 files / 40 unique | 5 fps | Not measured | Not measured | Not measured |
| Full held-out door layout | 9 | 5 fps | Not measured | Not measured | Not measured |

The first six-clip run used X-2/X-3, X-26/X-27 and X-40/X-43. It produced one temporal
hit at ±1/2/5 seconds, but the matching prediction had the wrong rule type; temporal
matching alone is not classification quality. The six clips all completed. The
subsequent X-26/X-27 pair completed with no findings: it missed the labelled cash
violation and correctly left the control clean. Uncached processing took 104.13 s
and 120.79 s respectively at 0.5 fps on the local Intel i5 CPU.

Artifacts are retained in `reports/v1-cpu/` (initial diagnostics),
`reports/final-pair/178ade69/` and the later desk-crop checks. They contain real local
model outputs, not manually supplied predictions. Low-fps runs are integration checks,
not a substitute for the intended 5-fps evaluation. Some initial-run observations
were cached; inspect `perception_cached` in per_video.csv before comparing timings.

The latest desk-crop pair, `reports/desk-crop-pair/f5b24ab0/`, produced a safe-open
finding at 18 s in X-40, whose labelled personal-item event is at 17 s, and no finding
in the correct X-43. This is another temporal match with the wrong primary rule,
not validation of W-NO-PERSONAL-ITEMS. Processing took 78.15 s and 174.27 s at 0.5 fps.

The earlier stage-1 stub processed all 42 files and verified duplicate/label handling,
but its scores are not model quality and are not used as the v1 result.

## Cloud GPU checks following the later migration request

The code, service, weights and supplied dataset are now on the user's existing Brev
`datathon` VM, following explicit approval to transfer the 42 hackathon clips and
workbooks. No external cloud AI API is used. The app and reports are accessed over
an SSH tunnel; no inference runs on the laptop.

NVIDIA L4: 23,034 MiB VRAM, driver 595.91.07, PyTorch 2.10.0+cu128. All four model
adapters passed with container networking disabled. Cold model loading took 12.63 s;
peak Torch allocation was 1,654.7 MiB. Three measured passes after warm-up averaged:

| Adapter | Device | Mean per pass |
| --- | --- | ---: |
| RT-DETR person detection | CUDA | 41.7 ms |
| OWLv2 scene grounding | CUDA | 188.2 ms |
| OWLv2 object prompts | CUDA | 180.6 ms |
| CLIP, all six state families | CUDA | 103.0 ms |
| RTMPose | CPU ONNX Runtime | 35.4 ms |

A generated 145-second gray clip at 5 fps completed in 127.48 s, including debug
rendering, with networking disabled. Its sparse scene does not establish the
worst-case runtime on bank clips. It overlapped the first real-video check near the
end, so it is not an isolated performance benchmark.

The real X-2 clip (17 s, 85 sampled frames) completed in 61.55 s. It produced
A-SECOND-PERSON at 10.0 s and A-OUTSIDER-ZONE at 12.8 s, with three evidence frames
each. The label is C-ID-BEFORE-CASH at 10 s: the primary rule was missed. Cash
coverage was false. This is a temporal match with the wrong rule, even at 5 fps.
The jury API separately processed X-2 uncached in 71.37 s and returned valid JPEG
evidence. Both checks ran during other validation work, so compare batch timings
when assessing speed.

The full 42-file / 40-unique-video batch is running at 5 fps in a detached offline
GPU container. Its progress and per-video results are live at port 8019; final
scores appear in `gpu/index.html` after completion. Do not replace the pending
full-dataset metrics above with the first clip's video-level success.

## Five known misses to expect

These are known cases, not a complete ranking from an unperformed GPU evaluation.

| Clip | Rule | Reason |
| --- | --- | --- |
| X-26, 9 s | L-NO-CASH-ON-LEAVE | The CPU check did not detect the small cash object confidently, so the rule could not fire. |
| X-1, 22 s | C-REJECT-NOT-RETURNED | Priority-2 rule is intentionally not implemented in v1; rejected-note provenance is also visually ambiguous. |
| X-47, 68 s | S-NO-MERGE | Priority-2 merge rule is intentionally not implemented; the duplicate video's 57 s event remains separately labelled. |
| X-44 | C-DETECTOR-CHECK | Explicitly excluded from v1 by the requested scope. |
| X-22 | L-SAFE-LOCKED-ON-LEAVE | Explicitly excluded; a physical safe lock is not established by visible open/closed state. |

W-NO-CAMERA-PHONE is also excluded as requested. All unsupported rules remain in the
codex and evaluation denominators. Candidate/indirect legal status is preserved.

## What remains unreliable

- Cash, bundles, cards and documents can be too small for general open-vocabulary
  detection. A second desk-crop pass helps resolution but did not fix X-26 in the
  measured CPU check. Instance-labelled fine-tuning is likely needed for bank cash.
- Automatic grounding can choose the wrong desk, safe or door. Review local debug
  overlays and use the per-video SHA-256 manual override when needed. No preset is
  selected by a training filename or a camera-layout label during inference.
- Earlier false outsider alerts came from using a leaning person's box centre.
  Position now prefers hip points, and an outsider root must be outside the desk
  surface. Occluded hips, tracking gaps and partial people can still misassign roles.
- Worn coats and held handbags can resemble desk items. Explicit overlap/hand guards
  reduce this error but do not establish contact with a physical table surface.
- CLIP crop states are zero-shot similarities, not calibrated probabilities. Safe/
  door state, screen state and machine activity may be wrong. Frame sampling and
  smoothing can delay transitions. A login-looking screen does not prove an OS lock.
- COUNT_END follows a visible classifier transition with tracked cash cues. Manual
  counting, brief counts, hidden feeds and attribution to a particular stack are not
  reliable. No banknotes are counted numerically and no bookkeeping is accessed.
- Bag inspection means sustained visible cashier hand contact; it does not establish
  actual seal integrity. Collector is a behaviour/position role, not an identity.
- Cash re-association is geometric. Nearby stacks, occlusion or track changes can
  break provenance or associate the wrong object. Unknown sessions do not prove
  that an ID was never shown before the video began.
- The default samples 5 fps; expensive object passes are scheduled every 0.4 s and
  crop states every 0.6 s, with tracking/smoothing between passes. These intervals
  are configurable. Faster sampling and a GPU do not by themselves fix semantic errors.

## Validation still needed on the target PC

The Brev L4 model adapters, CUDA image and cloud API have now been checked. Full
5-fps all-42 results, the full 9-clip held-out results and the longest bank video's
five-minute turnaround are still pending. A different target PC remains unverified.
Real frames were not submitted to cloud vision for visual review: debug MP4s are
rendered locally for the user's review; manual review of the training footage remains
outstanding. Model loading uses pinned local artifacts, offline mode and disabled
telemetry. Full-model inference passed in a container with `--network none`: six
sampled frames from X-20 completed in 131.92 s at 0.5 fps. The final CPU image also
passed an authenticated upload/poll/debug-download API check using a synthetic clip
and real models. There are 29 passing backend tests (rerun on Brev) and 3 passing frontend tests;
the frontend build, Ruff checks and CPU/GPU Compose configuration checks passed.

Freeze tuning using training-layout pairs before reporting held-out performance.
The current diagnostic split is not an independent generalisation result. Labels
identify primary scenarios, not exhaustive truth; extra real findings may be counted
as label-relative false alarms. One worker queues videos sequentially, so backlog
adds to the jury's end-to-end deadline. Uploads/results/caches have no automatic
retention policy; remove them explicitly when they are no longer needed.
