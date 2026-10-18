# A23 actual mirrored subset — completed API evaluation

**Parent integration completed:** all eight results are published at
http://localhost:8103/?run=a23-mirrored. All eight video range requests and trace
endpoints succeeded. The parent executed the reviewed validator outside the
worker sandbox, streamed the VM-private bundle to datathon2 and preserved all
85 original live/annotation/description files by hash. The sandbox blocker below
describes the historical worker handoff, not an outstanding publication problem.
`original-a21-reference.json` now contains the actual eight A21 originals (all
`no_violation`, 4/8 agreement); the original comparison below predates its arrival.

Actual8/8 terminal runs from the parent API batch; full coverage, each matching supplied video SHA256, perception_cache_hit=false and visual_cache_hits=0. Source main4a3b9ea is parent-attested and pinned local source files match; the API does not independently expose its server commit. Automatic/default camera overrides and safe-only4B are the parent-reported run settings. No API submission or GPU job was run by this worker.

**Verdict agreement5/8 (62.5%): TP1, FN3, FP0, TN4.** No failed/missing/invalid job was scored as clean. All8are included. X4 has two expected event rows but contributes one vote.

| Input | Expected | Actual | Outcome | API runtime s |
|---|---|---|---|---:|
| X-4_mirror.mov | violation | no_violation | FN | 150.936 |
| X-5_mirror.mov | no_violation | no_violation | TN | 117.721 |
| X-11_mirror.mov | violation | violation | TP | 31.219 |
| X-12_mirror.mov | no_violation | no_violation | TN | 53.738 |
| X-13_mirror.mov | violation | no_violation | FN | 72.489 |
| X-14_mirror.mov | no_violation | no_violation | TN | 147.060 |
| X-20_mirror.mov | violation | no_violation | FN | 20.167 |
| X-21_mirror.mov | no_violation | no_violation | TN | 27.189 |

Runtime: total620.520066s; median63.113494s; max150.935880s. There are143visual-check records,44unknown answers. Unknown does not establish a negative state. These check records are not claimed to be143neural generations.

The only positive is X11 A-OUTSIDER-ZONE@21s. Its binary verdict agrees with the expected violation, while the CSV describes an unlocked laptop. That is a different mechanism and is not a verified reason catch. No human-supported mechanism match is established by this batch; timing and all CSV norm/reason IDs remain unverified. X4, X13 and X20 are missed binary violations. No reason-accuracy percentage or legal validation is claimed.

Original-pair comparison is unavailable: the correct30/40 original per-input export was not supplied locally. Older32/40 and29/40 worker snapshots were not substituted. Pairing IDs and original hashes remain in the manifest, and the scorer reports missing originals explicitly. No invented before/after metrics.

## Private publication bundle

Actual completed and validated staging directory: `/tmp/a23-mirrored-publication/`. Its `realtime/` contains `state.a23-mirrored.json`, `state.a23-mirrored.meta.json`, and eight actual byte copies under `uploads/a23-mirrored-01.mov` through `-08.mov`. Each saved item was validated with the exact shared/a23/base `realtime.gateway.Item`, source=upload, stable IDs, actual raw result/job ID/verdict, and the supplied scoring label. The result objects are preserved; media were not decoded or transformed. Sibling `traces/<job_id>.json` files are untouched actual raw trace byte copies, source/destination SHA-verified. `metadata.json` holds allowlisted metrics/provenance. Directories are0700; every file0600. No archive was generated and no raw/media file was placed in the worktree or emitted through tools.

Timestamps are approximate presentation timestamps: finished_at=result file mtime; started_at=finished_at-reported runtime; queued_at=min(started_at,accepted file mtime-upload_s). Accepted/result mtimes and source hashes are documented in metadata.json.

**Filesystem blocker:** the sandbox mounts `/home/ubuntu/workspaces/datathon26-workers/shared/a23-mirrored/publication` read-only (actual mkdir returned errno30). No approval escalation or retry was attempted. Parent can create the requested shared layout outside the sandbox with this VM-local command, preserving private modes:

```bash
cp -a /tmp/a23-mirrored-publication /home/ubuntu/workspaces/datathon26-workers/shared/a23-mirrored/publication
```

Parent can then stream the resulting `publication/realtime/` and sibling `publication/traces/` directly VM3→VM2 over SSH without printing bytes. No existing live state or service was modified. This bundle is NOT yet published on :8103. The gateway serves a saved upload from `<state_dir>/uploads/<item_id>.mov`; preserving the filename/ID pairing avoids fallback to an original clip. Its saved trace route proxies the job ID to the checker; parent must install the actual trace files into the receiving checker trace directory only if that route is supported.

Actual validation: preparation verified8terminal rows, unique names, raw/accepted/job-ID agreement, input hashes, full successful coverage, fresh caches, pinned source hashes,8gateway Item models,8upload byte-copy hashes and8untouched trace hashes before final atomic directory rename. A focused post-write check verified8uploads/8traces, all0700/0600modes and equality of the standalone score with bundle metadata. Existing score.py CLI ran successfully on the real allowlisted data. No broad suite or GPU/API work.

Limits: these are horizontally flipped/re-encoded public development clips, not held-out independent scenes or a new camera angle. Inherited labels are evaluation-only; no clip/time/filename/clothing exception was added to runtime. Binary agreement does not validate the mechanism, timestamp or legal citation.
