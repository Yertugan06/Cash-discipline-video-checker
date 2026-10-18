# Context for agents

Working notes for coding agents on this project. Read before starting work.

## Repository status

- `github.com/Yertugan06/Hackathon` is a **draft** repo. The team will create a new repo
  with a fresh history for submission. Don't worry about what's tracked or pushed here
  (per-video labels, predictions, frames, history): commit what the work needs.
- Still applies: no cloud AI tools on dataset videos or frames (task.md §7), and never
  commit secrets (`.env`, API keys).

## Layout

- `STATUS.md` says what is current and what is history, where the labels come from, and
  which paths moved on 2026-10-17. `archive/` is history: don't build on it without moving
  the file back out.

## Results

- Current release: A21 builds on base main `2c5db9a`; reviewed source, tests and reports
  are published together in the implementation commits. Full final API validation is 30/40 unique verdicts, zero clean
  false alarms, 42/42 successful jobs; 9 findings compatible with human prose, 0 contradicted,
  3 unknown. A20's higher binary score included two contradicted explanations. Release/evidence:
  `attempts/A21-deadline/RESULTS.md`. The complete runtime is one VM (datathon2); the two-VM
  20+20 split was temporary evaluation only. Optional local state verification gave no finding
  improvement in the earlier full run. The user subsequently explicitly requested it on;
  Qwen3-VL-4B safe-state checks are enabled on datathon2; all 42 enabled API jobs passed,
  still 30/40 verdict agreement. Fresh inference was confirmed (40 calls; X20 cold
  smoke 50.669 s). Preserve all annotations and the
  raw results on that VM. The original main/public deployment on datathon was not replaced.

- Every approach tried, with its result and logs: `attempts/README.md` (the map). Add a row
  and a folder (copy `attempts/_template/`) for every new attempt, including failed ones.

## Experiments

- Rerun the rules on cached perception without the GPU: `scripts/replay_f1.py run`, then
  `score` and `timing` against `data/prepared/videos.jsonl`. Robustness without new videos:
  `run --zoom 0.8`, `--mirror`, `--drop 0.2 --seed N`. A change should leave these stable.
- Copy a perception cache with `tar` or `cp -a`, never `cp -r`: each clip folder holds several
  versions and the replay takes the newest by file time.
- Services and replays need `RULE_SCOPE=detector` until the norms in `knowledge/rulebook.yaml`
  are human-verified.
- The night orchestration of 2026-10-18 (A20) kept its working file, the team's description of
  every clip and the agents' reports in `attempts/A20-night-orchestration/` (`LAB.md`,
  `clip-descriptions.md`). The next step it left is the VLM checks (`attempts/README.md`).
- Historical pre-A21 checkpoint: main `7bc47e7` and annotation/run-browser work were integrated. Review:
  `attempts/A20-night-orchestration/reports/main-integration-and-annotation-audit.md`.
  Merged cached replay matches main's API verdicts and rule IDs: 32/40, zero clean false alarms,
  eight misses. Some positive clips have unsupported reasons; verdict agreement is not full
  explanation validation. The user explicitly switched to deadline implementation at 02:41 UTC
  with 3.5 hours remaining; four remote workers are assigned under `attempts/A21-deadline/`.
- User requests Claude Opus 5.5 at high effort for material design decisions when available.
  They explicitly approved sending the prepared text-only review packet containing selected
  project code, annotation excerpts and measured results. Keep raw videos/frames and credentials
  out of cloud consultations. Use a separate read-only session, verify the reported model, and
  record advisory feedback and measured evidence separately. Do not silently substitute a model.
  First project review completed and verified `claude-opus-5-5` with `--effort high`; report:
  `attempts/A20-night-orchestration/reports/opus-5-5-small-object-review.md`. Provisional next
  diagnostic compares current inputs with native object crops and short sequences before adding
  tracking. The report corrects an erroneous tracker-buffer claim using installed source.

## Manual video descriptions

Human descriptions received from Sultanbek on 2026-10-18 are archived verbatim in
`data/team/annotations/sultanbek-2026-10-18-part1.txt` (23 clips) and `part2.txt` with the same
prefix (16 clips), with clip mappings and review notes in their adjacent JSON files.
All 39 supplied descriptions were imported and read back verbatim on datathon2; the three
previously saved clips X-1, X-2, X-3 bring coverage to all 42 listed clips. Earlier annotations
were preserved. The source heading `xx47` maps to X-47; its original heading remains archived.
Preserve Russian wording, uncertainty qualifiers, occlusions, and clip cutoffs. X-11 and X-12
have identical supplied descriptions; retain both and recheck their mapping before treating
them as a contrast pair. X-35's suspected counterfeit/occluded detector contact, X-39's hidden
key state, and X-48's hidden cash/hand-position inference are not direct visual confirmations.
These are whole-clip observations, without invented event times or inferred violation verdicts.
The user clarifies that filming used one fixed camera position/angle, with multiple setups and
scenario groups. References to the previous video supply setup context; cross-file transaction
continuity is unspecified. X-43/X-45 stop after counting, so later storage or abandonment is
unknown. Preserve recording boundaries and distinguish omitted/occluded actions from observed
failures. The annotation audit records this distinction without changing the original prose.
Later X-1 clarification is in `data/team/annotations/sultanbek-2026-10-18-clarifications.json`:
the user reports all notes accepted by the counter, then hand-counted and partly returned near
the organizer's 22 s marker. The label is retained; its reason is unresolved. The earlier
rejected-note explanation was tentative and must not be treated as established evidence.
The user subsequently confirms that the notes/hand count in X-1 are clearly visible to a human
observer. The earlier out-of-view-counting hypothesis is unsupported too; the cause remains open.
Answering the paused-frame question, the user confirms that ID documents and money are visually
distinguishable with certainty to a human. This supports the existing crop-first diagnostic;
model recognition and sampling coverage still require measurement. The user then corrects the
earlier ID-first claim: in clean-labeled X-19 the first client hands over cash without first showing
ID, while the second client shows ID. The blanket requirement is no longer confirmed by the user;
actual applicability remains unresolved. This does not prove that identification is never required.
Keep `C-ID-BEFORE-CASH` provisional with unverified scope in the design audit pending review;
its canonical YAML still says enabled/business-confirmed with pending citations, and runtime code
has not been changed during grilling. Do not add a clip exception, relabel X-19, borrow the second
client's ID for the first, or turn an ID detection miss into proof of no presentation.
A follow-up Opus review of this rule-evidence question initially required separate payload approval.
The user explicitly approved `/tmp/datathon26-rule-evidence-review-packet.txt` with yes, and that
exact packet was then sent successfully to verified `claude-opus-5-5` with `--effort high`.
Report: `attempts/A20-night-orchestration/reports/opus-5-5-id-rule-review.md`. No approval blocker
remains for this completed consultation. Advice is to preserve facts/labels, verify policy scope
and coverage, and avoid per-file exceptions; no runtime change or new performance claim followed.
X-4's 57 s clarification: first client has already left, his cash remains on the table, and the
user describes brief visibility while it is moved between sides. The candidate explanation is
previously accepted cash not put into storage (231 paragraph 20, second paragraph), not movement
or occlusion itself. The user now confirms client 2 touches the door at 55 s and is inside closing
it at 57 s, while client 1's cash remains on the desk. This supports `S-CLEAN-DESK-HANDOVER` around
57 s: next client enters with previous-session cash still on the desk. Door contact alone is not
entry. X-4/X-47 are identical files with separate organizer markers 57/68 s; do not conflate this
entry event with later cash mixing or encode a fixed time/desk side. These are human observations,
not a fresh model result or independently confirmed organizer explanation; runtime is unchanged.
The user further confirms that client 2's cash is placed directly on client 1's remaining pile,
then the cashier uses the laptop. This supports a distinct `S-NO-MERGE` observation; exact stacking
time is not supplied. Do not infer that the new cash is never counted later or that laptop use is
itself a violation. The latest wording says "id after money", conflicting with the earlier ID-first
description, but the user immediately clarified explicitly: "ID first, then money." This resolves
the ambiguity and restores the evidence contradiction to the current missing-prior-ID finding.
Keep the entry/uncleared-cash and later stacking events separate; no exact stacking time is supplied.
The next experiment is specified in
`attempts/A20-night-orchestration/reports/next-cash-workflow-experiment.md`: compare current
inputs with native-source tiles and short sequences using existing A13 presence labels, then
conditionally validate cash history on paired client scenarios. A13 has no oracle object boxes;
do not claim a localization-controlled recognition ceiling. Planning only: no inference was
started at spec creation. The subsequent explicit user instruction now authorizes implementation;
see `attempts/A21-deadline/README.md` and its shared/worker briefs for current ownership.
A numeric re-score of A13's saved answers clarifies that 4/11 cash is accuracy, not recall:
OWLv2 and the 7B VLM found 0/7 cash-positive frames (0/4 negative false positives); Grounding
DINO found 1/7 (1/4 false positive). ID has just one positive and one negative answer. Counts and
source hashes: `attempts/A20-night-orchestration/logs/a13-small-object-rescore.json`; no inference
or dataset image viewing was performed for this re-score.

## Machines

- `datathon` (Brev, L4): live service in `~/datathon26`, compose project `datathon26`,
  `DETECTOR=f1`, `RULE_SCOPE=detector`, on port 8000 with `API_HOST=0.0.0.0`, public only
  through Brev's proxy at `https://forte-checker-wwi4jcrss.gobrev.dev` (`deploy/README.md`).
  Deployed: `277ac67` (mov/mp4/mkv uploads). Rollback image of the previous version (`5d8f0bf`):
  `forte-cash-checker:cuda-5d8f0bf`; gateway: `datathon26-realtime:pre-277ac67`.
  No git checkout there: deploy by piping
  `git archive HEAD` (plus uncommitted files) over ssh. What's deployed is in
  `~/datathon26/DEPLOYED_COMMIT`.
  Live verdict page: container `datathon26-realtime` (image built from `realtime/Dockerfile`,
  gateway on `127.0.0.1:8100`, WebSocket feed, runs `~/data/open/videos` one at a time,
  results persisted in `~/realtime-state/state.json`). View it with
  `ssh -N -L 8100:127.0.0.1:8100 datathon` -> http://localhost:8100. Open a result to replay
  the video with the detector's boxes and roles drawn over it ("Objects" toggle).
  `/compare` shows saved runs side by side; `/annotate` is where the team writes what really
  happens in each clip (blind; saved on the VM in `~/realtime-state/annotations/<clip>.json`,
  scored against a run's traces per action). Those files are the event-level ground truth.
  Debugging a verdict: every F1 job writes `/app/runtime/traces/<job_id>.json` in the checker
  (volume `datathon26_work`): calibration candidates, raw state changes, the event log (roles,
  enter/exit, safe/door/screen), every rule finding with `kept`, per-frame boxes. Also served
  at `GET /api/v1/jobs/{job_id}/trace`. `docker logs datathon26-checker-1` has one line per job
  stage. To rerun the rules on cached perception without the GPU, see `scripts/replay_f1.py`.
  Team data root: `~/data` (`open/` organizer data, `team/` team workbooks and reviews); the
  canonical copy for `python -m eval.sync_data`. Add files there, never overwrite.
  To test a branch without touching the live service, run a second container from the same
  image on another loopback port (A20 used `night-checker` on 8001 with its own copy of the
  perception cache) and drive it with `attempts/A20-night-orchestration/spikes/api_run.py`,
  or with a second gateway from the `datathon26-realtime` image on another port. The gateway
  finds its checker through `CHECKER_URL` (default `http://127.0.0.1:8000`, the live service),
  not `API_HOST`/`API_PORT`; with the wrong URL every job fails with 401.

- `datathon2` (Brev, L4): current A21 runtime in
  `~/workspaces/datathon26-workers/shared/a21/candidate`, checker 8003 and gateway 8103.
  F1 plus local Qwen3-VL-4B safe-state checks run on this one VM. Tunnel 8103 opens
  `/evaluation`, `/annotate` and `/compare`; startup: `realtime/README.md`.
  Latest 42 annotations and 42 drafts are in `runtime/realtime/` there; raw API results,
  traces, weights and model environments also stay on this VM. The old 8002/8102
  preview is stopped and both annotation copies were backed up during cutover.
  Annotation text and labels never feed inference. Description mode needs no exact
  timelines, and new drafts never overwrite human edits. Generic config is opt-in;
  the A21 launcher enables VLM checks by default at the user's explicit request.
  Datathon3 was used for a temporary 20+20 perception split, not runtime dependency.
- `datathon3` (Brev, L4, 4 vCPUs, 16 GB RAM): development Git checkout at
  `~/workspaces/datathon26`. Connect with
  `ssh -t datathon3 '~/.local/bin/datathon'`.
  Persistent tmux session `datathon26` has `codex`, `shell`, and `tests` windows;
  detach with Ctrl-b, then d. The helper recreates the session if needed.
  Codex 0.163.0 is signed in through device login, uses `gpt-6.1-sol` with `max`
  reasoning, Context7 MCP, and a limit of two concurrent subagents.
  Settings: `~/.codex/config.toml`, `~/.codex/AGENTS.md`, `~/.tmux.conf`.
  Python 3.12 and CUDA 12.8 PyTorch are in `.venv`; Node 24 is on PATH.
  CUDA works in the VM shell; GPU commands from Codex require approval outside
  its filesystem sandbox. Run GPU-heavy jobs one at a time.
  Historical, completed annotation preprocessing (2026-10-18): a separate worker in
  `~/datathon26-annotation-prefetch` finished warming the detector's perception for 14
  later clips. It uses its own code snapshot, model weights, videos and cache, and the
  existing checkout's Python environment. Progress/PID/log: `runtime/progress.json`,
  `runtime/worker.pid`, `runtime/worker.log`. A laptop process
  `/tmp/datathon_annotation_prefetch_sync.py` validates matching cache fingerprints and
  atomically publishes completed perception to `datathon2`'s preview cache. Its status/log
  are `/tmp/datathon-annotation-prefetch-sync.json` and `.log`. Annotation files stay on
  `datathon2`; all 14 caches synced successfully and its sequential queue finished all 42 clips.
  Source is commit `0ab0258` plus the uncommitted code snapshot recorded in
  `.git/datathon3-snapshot.json`; there is no automatic sync with the laptop.
  Initial validation: frontend tests/build and backend Ruff pass; pytest has
  305 passed, 7 skipped, and 2 failures (desk-history leave rule and pipeline
  evidence-frame extraction). Logs: `~/.cache/datathon3-bootstrap/`.

## Remote implementation worker pool

The user wants one orchestrator working with them and four remote implementation
workers: two on `datathon2`, two on `datathon3`. Both VMs now have Codex signed in.
The orchestrator dispatches tasks over SSH and reviews returned reports and patches;
native subagent spawning does not choose between VMs.

Each VM has `~/workspaces/datathon26-workers/worker-1` and `worker-2`, separate
Git worktrees and Python/CUDA/frontend environments, from committed main `7bc47e7`.
Branches are `implementation/<VM>-worker-<slot>`. The `implementation` Codex profile
disables nested agents. The launcher serializes tasks per slot, allowing two active
managed workers per VM. Submitted jobs persist under the separate tmux server
`codex-workers`, session `implementation`.

Interface: `~/.local/bin/codex-worker submit|resume|status|result SLOT TASK_ID`.
Submission reads its task brief from stdin. Reports, tracked patches, new-file
archives, events, and logs are in `~/workspaces/datathon26-workers/runs/`.
Review and commit a worker's changes before assigning it another task.
Full usage: [`docs/REMOTE_WORKERS.md`](docs/REMOTE_WORKERS.md).

All four slots passed real Codex dispatch, remote command execution, workspace
write/read/delete, report collection, clean-tree, and lock-release checks.
Input checks reject invalid slots, path traversal, and empty task briefs.
GPU-heavy jobs share one L4 per VM and require coordinated, approved execution
outside the filesystem sandbox when NVIDIA devices are needed.
