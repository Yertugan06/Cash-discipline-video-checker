# ORCH-sessions - client-session rules from cached perception

- **Date / branch:** 2026-10-18, `orch/sessions`
- **Status:** measured offline; not deployed
- **Models:** unchanged F1 perception cache; no GPU, dataset video/image, network, or VM access

Recognize sustained service of two clients, count-in-progress at a confirmed client exit,
and standing/seated client track continuity. Extend workstation calibration using existing
hand-contact evidence when the laptop is too far from the cashier's hips. Preserve established
calibration and measure departure from the learned working position in the new layouts.

| Metric, 40 unique cached clips | Before | After |
|---|---:|---:|
| Correct | 25 | 28 |
| Clean false alarms | 5 | 5 |
| Missed violations | 10 | 7 |

New catches: X-18 at 19.5 s, X-38 at 32.0 s, X-34 at 15.0 s. No other kept finding changes.
X-4/X-47 keeps its ID-before-cash finding at 66.0 s. X-2 remains missed: no cash or bundle
appears in its 34 cached samples. All 19 unique clean clips have zero assigned-rule findings.

See [the full report](../../REPORT-ORCH.md) for target evidence, clean controls, timestamps,
shared interfaces, rejected trials, and verification: 90 tests passed, one GPU test skipped;
affected F1 code/tests pass Ruff. Repository-wide historical lint errors remain untouched.

Reproduce without `--videos-dir`:

```bash
export API_KEY=x PYTHONPATH=.
ORCH_ROOT=/tmp/claude-1000/-home-sultanbek-projects-hackathons-datathon26/63bd15ca-5dd2-4bc8-a818-01aa3c847602/scratchpad/orch
PY=$ORCH_ROOT/venv/bin/python
$PY scripts/replay_f1.py run --cache-dir "$ORCH_ROOT/perception_cache" > /tmp/sessions-after.jsonl
$PY scripts/replay_f1.py score /tmp/sessions-after.jsonl --labels data/prepared/videos.jsonl
$PY -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
```

Local diagnostic outputs remain under `/tmp/sessions-*`; generated replay files are not committed.
