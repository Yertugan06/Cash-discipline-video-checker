# A10 - agentA rulebook variant

- **Date:** 2026-10-17
- **Status:** ran on the dev split; **no score recorded** (no score file found on either VM)
- **Where it ran:** `datathon2`, `~/agentA-rulebook` (copy at `datathon:~/from-datathon2/agentA-rulebook/`), uncommitted `signals.py` + `agentA_*.py` scripts
- **Models:** as A01 (F1 stack)

## Approach

The F1 checker with a rewritten rulebook and extra signals. Scripts: `agentA_features.py`,
`agentA_probe.py`, `agentA_rulestats.py`, `agentA_eval.py`.

## Results

`logs/full_dev.log` shows the dev videos ran without errors (11.7-81.6 s each). No verdict
scores were saved. Run outputs: `datathon:~/from-datathon2/agentA-rulebook/runtime/agentA_runs/`.

## Next

Score `agentA_runs` with `eval/run_eval.py` before deciding whether any of its rules go into A12.
