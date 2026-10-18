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

## Machines

- `datathon` (Brev, L4): live service in `~/datathon26`, compose project `datathon26`,
  `DETECTOR=f1`, loopback `127.0.0.1:8000` only. No git checkout there: deploy by piping
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
- `datathon2` (Brev, L4): stopped; its home is copied to `datathon:~/from-datathon2/`.
