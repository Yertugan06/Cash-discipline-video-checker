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

## Machines

- `datathon` (Brev, L4): live service in `~/datathon26`, compose project `datathon26`,
  `DETECTOR=f1`, loopback `127.0.0.1:8000` only. No git checkout there: deploy by piping
  `git archive HEAD` (plus uncommitted files) over ssh. What's deployed is in
  `~/datathon26/DEPLOYED_COMMIT`.
  Live verdict page: container `datathon26-realtime` (image built from `realtime/Dockerfile`,
  gateway on `127.0.0.1:8100`, WebSocket feed, runs `~/data/open/videos` one at a time,
  results persisted in `~/realtime-state/state.json`). View it with
  `ssh -N -L 8100:127.0.0.1:8100 datathon` -> http://localhost:8100.
- `datathon2` (Brev, L4): stopped; its home is copied to `datathon:~/from-datathon2/`.
