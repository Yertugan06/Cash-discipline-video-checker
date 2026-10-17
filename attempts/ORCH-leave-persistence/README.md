# ORCH-L - Persistent leave evidence and confirmation of the absence

- **Date / who:** 2026-10-18, `orch/leave` implementer
- **Status:** measured offline
- **Where it ran:** local CPU replay, baseline `ac6fe47` from `night`
- **Models:** unchanged from A17; cached perception only

Item leave rules require an away interval lasting through the existing two-second confirmation delay, then corroborate the same object track in at least two observations in each of two short windows. This removes a short false departure while preserving detections when an exact check frame is lost. Other leave-rule callers retain their prior departure semantics.

| Run | Correct /40 before -> after | Clean FP before -> after | Missed before -> after |
|---|---|---|---|
| Full | 26 -> 27 | 4 -> 3 | 10 -> 10 |
| Drop 0.2, seed 0 | 24 -> 26 | 2 -> 1 | 14 -> 13 |
| Drop 0.2, seed 1 | 27 -> 27 | 2 -> 2 | 11 -> 11 |
| Drop 0.2, seed 2 | 25 -> 26 | 3 -> 2 | 12 -> 12 |
| Loss-seed mean | 25.33 -> 26.33 | 2.33 -> 1.67 | 12.33 -> 12.00 |

No verdict regressions. Х-26's finding moves to 12.5 s, versus organizer 9 s. Х-20's retained documents finding is incidental to the organizer's open-safe violation. Details, evidence counts, all changed findings, timecode offsets, and limitations are in [REPORT-ORCH.md](../../REPORT-ORCH.md).

Reproduce from the repository root, without videos or a GPU:

```bash
export API_KEY=x PYTHONPATH=.
ORCH_ROOT=/tmp/claude-1000/-home-sultanbek-projects-hackathons-datathon26/63bd15ca-5dd2-4bc8-a818-01aa3c847602/scratchpad/orch
PY="$ORCH_ROOT/venv/bin/python"
"$PY" scripts/replay_f1.py run --cache-dir "$ORCH_ROOT/perception_cache" > /tmp/leave-after-full.jsonl
"$PY" scripts/replay_f1.py score /tmp/leave-after-full.jsonl --labels data/prepared/videos.jsonl
for seed in 0 1 2; do
    "$PY" scripts/replay_f1.py run --cache-dir "$ORCH_ROOT/perception_cache" \
        --drop 0.2 --seed "$seed" > "/tmp/leave-after-drop$seed.jsonl"
    "$PY" scripts/replay_f1.py score "/tmp/leave-after-drop$seed.jsonl" --labels data/prepared/videos.jsonl
done
"$PY" -m pytest -q -rs tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
"$PY" -m ruff check backend/f1/rules.py tests/test_f1_rules.py
"$PY" -m ruff format --check backend/f1/rules.py tests/test_f1_rules.py
```

Validation: 94 passed, one existing model-weight test skipped. All 16 new cases fail against the baseline implementation. Modified-file Ruff checks pass; whole-repository Ruff has 480 existing errors in historical attempts and validation scripts. Logs are listed in the root report.
