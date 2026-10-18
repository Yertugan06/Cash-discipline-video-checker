# Current annotation and evaluation handoff

Updated 2026-10-18 for A21. The base main is `2c5db9a`; reviewed source, tests and
results are published together. The earlier design interview ended before implementation.
The complete runtime is **one VM, datathon2**: checker 8003 and gateway/tunnel 8103.
The old 8002/8102 preview is stopped. The existing public A20 deployment on datathon
was not replaced by this release.

## Start here

- [Release/results/source hashes](../attempts/A21-deadline/RESULTS.md).
- [Startup and tunnel](README.md#current-one-vm-review-service).
- [Evaluation](http://localhost:8103/evaluation), [annotation](http://localhost:8103/annotate),
  [saved comparisons](http://localhost:8103/compare).
- Remote source: `~/workspaces/datathon26-workers/shared/a21/candidate`.
- Live data: `runtime/realtime/` there; 42 annotations and 42 description drafts retained.
  The cutover backup preserves both copies under `shared/a21/annotation-cutover-backup`.

## Current behaviour

The easy annotation view uses one editable whole-clip description; exact timelines are
optional. Autosave/version conflict handling, manual text, AI provenance, object/event
review and saved-run browsing remain intact. Annotation text and organizer labels never
reach checker inference. All descriptions retain uncertainty and recording cutoffs.

F1 has local Qwen3-VL-4B **safe-state checks enabled** at the user's request. This is
`F1_VISUAL_CHECKS=1`, not the alternative top-level `DETECTOR=vlm`. The helper does not
supply cash/ID detections. Door checks remain diagnostic; laptop is not in the enabled family.
Desk-object history remains experimental and false by default; its strict configuration
compatibility was restored and all 15 existing checks pass.

## Actual validation

- Current VLM-enabled API: 42/42 successful jobs, 30/40 unique matching verdicts,
  11/21 violation clips caught, 10 missed, 0/19 clean false alarms.
- Findings: 9 compatible with human prose, 0 contradicted, 3 unknown; this is not legal validation.
- Model execution: 40 fresh VLM calls, 476 answer-cache hits, 41 perception hits.
  Forced-cold X20: 50.669 s, 23/23 samples and 23 fresh known state answers, no errors.
- Twelve evidence JPEGs decoded; 13 pinned runtime files match deployment.
- Historical A20: 32/40 with two contradicted explanations. Current supported finding
  count remains 9; no detection improvement is claimed. All public clips influenced development.
- Existing targeted checks: 108 event/evidence/integration, 43 API/realtime/export,
  14 scorer and 15 legacy configuration checks passed in their recorded environments.
  No new full-suite claim. Legal citations remain pending and jury scope is gated.

## Preservation

Raw Russian messages/mappings remain in gitignored `data/team/annotations/` and on the VM.
Earlier backups and scoped stashes are retained; see the release report. Workbook edits,
editor settings and generated binary/cache files are unrelated to these implementation commits.
Do not overwrite annotations, deploy stale 8102 instructions, or treat cached timings as cold inference.
