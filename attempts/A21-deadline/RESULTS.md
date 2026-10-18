# A21 release and experiment results

The final checker, evidence generation, local Qwen3-VL-4B safe-state checks and realtime
gateway run together on **datathon2**. The user explicitly requested the VLM enabled after
the no-VLM validation; the enabled release has now completed all 42 jobs successfully.
The temporary 20+20 split between datathon2/datathon3 only accelerated evaluation.
Source builds on base main `2c5db9a`; reviewed code, tests and this evidence are published together.

- Review: <http://localhost:8103/evaluation>. Each clip links to its watch/comment page.
- Live results: <http://localhost:8103/>; saved comparisons: <http://localhost:8103/compare>.
- Exact deployed source: [manifest](final-source-manifest.json).
- Actual final API results: [current numeric records](vlm-enabled-api.jsonl), [current audit](vlm-enabled-api.audit.md).

## What changed and what it gave

| Change | Measured result / limit |
|---|---|
| Missing ID detection no longer proves non-presentation; generic documents remain distinct from ID cards | Removes X4/X47's contradicted ID accusation. The blanket ID-first policy remains unresolved. |
| Documents/laptop rules require room-exit evidence; cash/bag rules retain workstation-absence scope | Removes X20's contradicted documents-on-exit explanation. Walking to equipment does not become a room exit. |
| Door-reaching hands can corroborate an observed departure when hips miss the calibrated doorway; an overlapping replacement track blocks the added path | Recovers X28's laptop finding at 14 s. Only X28 changes in the full fresh-40 replay; no filename/time exceptions. |
| Cash ownership expires across long observation gaps; prior-session cash and physical stacking remain distinct | Keeps X38's supported handover finding; does not manufacture X4 cash detections or claim stacking from co-presence. |
| Recording cutoffs and unknown observations remain explicit | X43/X45 do not become abandonment violations because the recording ends. |
| Independent observation audit, evaluation page, links to annotation, saved-run comparison | Reports verdict agreement separately from supported/contradicted/unknown findings. All 42 existing annotation descriptions are preserved. |
| Merge current main | Preserves .mov/.mp4/.mkv acceptance, citation scorer/export, public deployment configuration and the existing realtime features. |

## Results

| Run | Unique agreement | TP / FN / FP / TN | Finding compatibility with human observations |
|---|---|---|---|
| A20 baseline | 32/40 | 13 / 8 / 0 / 19 | 9 supported, 2 contradicted, 3 unknown |
| Evidence guards before exit correction | 29/40 | 10 / 11 / 0 / 19 | 8 supported, 0 contradicted, 3 unknown |
| No-VLM real API, reviewed exit correction | 30/40 | 11 / 10 / 0 / 19 | 9 supported, 0 contradicted, 3 unknown |
| **Current enabled-VLM release, actual API** | **30/40** | **11 / 10 / 0 / 19** | **9 supported, 0 contradicted, 3 unknown** |

These are 42 files in 40 SHA groups. X4/X47 and X5/X48 are byte duplicates; distinct
organizer markers remain in the audit. “Supported” means compatible with supplied prose,
including qualified proxies, not verified legal applicability or complete reason accuracy.
All these public clips influenced development; this is not an unseen-camera benchmark.

## Local model experiments

No dataset image/video was sent to cloud AI. Actual GPU calls ran on the authorized VMs.

| Experiment | Actual evidence | Decision |
|---|---|---|
| OWLv2 full frame / desk / native tiles, fixed 20 inputs | Full+desk and full+desk+tiles both identify 5/7 labelled cash positives; both miss 2. Four labelled cash negatives remain clear. Main already uses desk crops. | No additional cash gain from tiles; no runtime change. Sparse frame labels are not box/track truth. |
| Qwen3-VL-4B full frame / 384 px tiles / three-frame tiles, fixed 12 inputs | 156 real calls. Cash TP 2 / 3 / 2; 8 / 8 / 9 labelled cases unknown. All four cash negatives remain unknown. Temporal input creates one false ID answer. | Not promoted as a cash/ID detector. Unknowns are not true negatives. |
| Event-selected safe verifier, full 42-file API pass | 461 actual inference calls, 39 answer-cache hits, 23 unknown checks. **No verdict/finding change** from the same pre-exit-fix pipeline without verification. Cached API median 7.593 s. | `F1_VISUAL_CHECKS=1` is now **enabled at the user's request**. The earlier comparison found no gain. Door checks remain diagnostic after a false-open answer on clean X31. |

Raw numeric model results and fixed input/source manifests are under [recognition](recognition/).
The safe follow-up and consumer review are under [visual](visual/); the exit review is under
[exit-review](exit-review/). The optional backend is retained for reproducible diagnostics;
it supplies no cash/ID detections and adds no multi-VM runtime requirement. It is now
enabled at the user's request; the earlier decision to leave it off is historical.

## Validation and runtime

- Fresh canonical GPU perception: 40/40 unique clips, 2,601 observations, no cache reuse;
  [shard measurements](parallel-perception-summary.json), [cache hashes](fresh-cache-manifest.json).
- Current enabled API: 42/42 successful jobs and all 12 returned evidence JPEGs decoded;
  [current schema/source check](vlm-enabled-validation.json). All 13 pinned runtime files match deployment.
- Historical no-VLM cached API: median **2.05 s**, maximum **6.276 s**, 42 perception hits.
  Current enabled run: median **2.0675 s**, maximum **50.669 s**, 41 perception hits and
  one forced-cold clip; neither median measures general cold video inference.
- A separate cold diagnostic candidate with the optional safe verifier processed X39 in
  **137.9 s**, 157/157 samples; [record](cold-api-summary.json).
- Earlier no-VLM release, longest clip X14 (**142.533 s video**): **158.6 s cold**, all **285/285**
  samples, no deadline hit, no perception reuse and no optional VLM calls; [record](cold-final-summary.json).
- Relevant checks: 108 event/evidence/integration tests passed on Python 3.12; 43 API/realtime/export
  checks passed there. Fourteen scorer checks skipped in the minimal deployment bundle because its
  R1 harness was absent; those same 14 passed in the full local checkout. Ruff and diff checks passed.
  No new full-suite run. The local Python 3.14 HTTP test run stalled and was stopped; it is not counted.

## Operation and preserved work

Remote source: `~/workspaces/datathon26-workers/shared/a21/candidate`.
The existing `boot_candidate.py` next to it starts the complete loopback checker on 8003
and realtime gateway on 8103. Its default now enables VLM verification per the user's explicit request;
`--no-visual-checks` disables it. All weights and environments are on the same VM. It generates a
private mode-0600 `runtime/service-key`; no credentials are in source or browser responses.

The gateway's `runtime/realtime/` contains the final `state.live.json`, preserved baseline and
verifier comparisons, `evaluation.json`, annotations and description drafts. Raw API results and
evidence images remain on the VM. The local report exports only allowlisted metadata.

Main was fast-forwarded using a scoped backup/stash; unrelated workbook, editor and binary edits
are preserved. Backup: `/tmp/a21-main-update-preserved-20261018T0339Z`; stash
`be4dd7e130c8eec1225df904ea3b71a5e5f98c4a`. The user requested publication of the current
implementation; unrelated workbook, editor, binary/cache and dependency-lock edits remain outside it.

## Remaining gaps

Ten violation clips remain missed. Cash/ID localization and ownership in X4, safe attendance,
screen readability, key-after-exit and rejected-note handling still need stronger observations.
X1/X2's violation causes remain unresolved. No timepoint, layout, filename or annotation lookup
was added to runtime inference. Three reported findings have unknown observation support.
All 12 returned legal citations remain pending human verification; jury scope remains gated.

The replaced 8102 tunnel, old annotation gateway/checker, completed worker monitor,
unused checkpoint transfer and isolated smoke browser were closed. The final 8103 tunnel
is retained with a gateway-log follow session; all worker worktrees and annotation backups remain.

The existing strict `desk_objects` configuration option was restored after a focused
compatibility failure; all 15 existing checks pass, and it stays false by default. The
neural/association code is AST-identical. Forty canonical fresh numeric payloads were
explicitly reused under the new conservative source fingerprint; payload hashes and the
proof are in `cache-compatibility-reuse.json`. No new neural inference is claimed for
that copy. X20 is forced cold again in the enabled-VLM run.

Portable combined code: [reviewed-source.patch](reviewed-source.patch), checked against
clean main `2c5db9a`. Unrelated workbook/editor/cache changes are excluded.

## User-requested VLM enablement — completed

Qwen3-VL-4B safe-state checks are on by default in the one-VM launcher. All **42/42**
current API jobs succeeded. Actual new inference: **40 VLM calls**, plus **476** prior
answer-cache hits; **41** perception hits. The forced-cold X20 smoke took **50.669 s**,
processed all **23** samples and produced **23** fresh known state answers, without errors.
The complete enabled run had **9** unknown state answers and no check errors. All **12**
returned evidence JPEGs decoded correctly; all **13** pinned source files match deployment.
Median enabled-run latency **2.0675 s** includes predominantly cached work; maximum
**50.669 s** is the forced-cold smoke. Accuracy remains **30/40**, with **0/19** clean
false alarms. The earlier 158.6-second longest-clip result had the VLM off; it is not
a measured longest-clip cold latency for this enabled configuration.
