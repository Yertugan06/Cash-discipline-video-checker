# Frozen temporal safe-action pilot — GPU_RUN_READY

Prepared 2026-10-18 04:38 UTC; no GPU run by this worker. Scope is only this owned
pilot directory. No backend hook, rule, service, environment or dependency changes.

Stage this directory on **datathon3** at
`/home/ubuntu/workspaces/datathon26-workers/shared/a22/safe-probe`, then execute the
exact `argv` in `gpu-command.json` after the offline Qwen3-VL-8B-Instruct weights
are ready. It holds the shared flock and a 600-s total timeout. The small launcher
uses only existing compatible Python environments, reports the selected Python,
and accepts an explicit `SAFE_PROBE_PYTHON`; it never installs or downloads.
Datathon3's interpreter paths cannot be verified here (read-only SSH attempt failed
on system ssh-config permissions). The launcher validates metadata on that VM.

Frozen **before inference** in `manifest.json`: six cases X20/X21/X8/X14/X27/X39
(X5 omitted to respect max6), prompt, image budget, sampling and generation budget.
Cases choose evaluation inputs only. No case name, filename, outcome, CV state,
time marker or annotation is included in the model prompt.

Generic selection: first stable COUNT_START after a same-actor HAND_ON_SAFE,
SAFE_OPEN or geometry-only safe-departure candidate; three actual counter-running
observations at t,t+0.5,t+1 with one same visible cashier. Missing role, calibration,
counter episode, complete triplet or prior safe candidate => explicit no-trigger /
unknown, with no time substitution. CV candidates are not assumed actual handling.

The model receives six ordered in-memory images: full native frame then calibrated
safe crop at each of three moments. Decoder source dimensions, decoded/requested
times, RGB hashes, crop pixel boxes and image-grid/token counts are recorded.
No image files are written or sent off-VM. Processor pixel limits reuse the A21
Qwen probe (65536–524288 pixels/image); full frames are not pre-resized by this pilot.

Prompt asks visible action only: safe_handling / table_counter_work / unknown,
plus independent safe door open / closed / unknown for each moment. Projection,
occlusion or insufficient visible action => unknown. No percentage confidence,
rule/legal/violation question or attendance policy. Raw CV fixture boxes, posture,
states, complete pose and trigger selection are saved separately in
`cv-selection.json`; the model answer and raw text go to `results.json`.

Reuse: native decoder, hash-selected cache calibration, role/event builders and
sanitized diagnostics come from shared A22 base/A21 recognition helpers. Model
load/template/generate/decode uses the existing offline Qwen3-VL bf16/SDPA path.
CPU self-check: `python pilot.py --self-check`. CPU selection-only mode appends
`--plan-only` and performs no decode, model loading or inference.

No accuracy/held-out/attendance claim: all40 public clips influenced development.
This is a six-case scene/action input pilot, not permission to promote a rule.

CPU results at 04:38 UTC: the single parser/selection self-check passed, Ruff
passed, and numeric selection-only run completed without decoding or models.
X20 selected 7.0/7.5/8.0 s from its actual stable counter episode. X21/X8/X14/X27/X39
returned no-trigger under the same frozen selector; no alternate times were
inserted. Their raw CV candidate events, counter state/score timelines and role
availability are recorded for diagnosing the missing context. This pilot cannot
claim a clean-pair comparison when the clean input has no valid trigger.

`safe-probe-files.tar.gz` extracts a `safe-probe/` directory; unpack under
`/home/ubuntu/workspaces/datathon26-workers/shared/a22` on datathon3. Model weights
and interpreter availability on datathon3 remain runtime prerequisites. Only the
parent executes the GPU argv; no sandbox CUDA test or production change was made.
