# A21 - F1 scene distances relative to the calibrated desk

- **Date / who:** 2026-10-18, scale implementer on `orch/scale`
- **Status:** measured offline, not deployed
- **Where it ran:** local CPU replay, starting at `c723ff6` (night baseline)
- **Models:** unchanged cached F1 perception; no model execution

The full [implementation report](../../REPORT-ORCH.md) contains the before/after score
JSON, per-clip evidence, finding times, failed intermediate approach, tests, and merge notes.

Every physical margin uses the desk's long side divided by the common 0.70 reference.
The fixed laptop-on-desk margin needed the same conversion before desk clustering.
Full data, all four requested zooms, and mirror score 31/40 with no clean false alarms.
Drop 0.2 seeds 0/1/2 remain 30/31/31. Full-data findings and all zoomed findings agree
exactly, including timestamps.

Reproduce without videos or a GPU:

```bash
export API_KEY=x PYTHONPATH=.
PY=/home/sultanbek/projects/hackathons/dt26-lab/venv/bin/python
$PY scripts/replay_f1.py run \
  --cache-dir /home/sultanbek/projects/hackathons/dt26-lab/perception_cache \
  --zoom 0.8 > /tmp/scale-replay.jsonl
$PY scripts/replay_f1.py score /tmp/scale-replay.jsonl --labels data/prepared/videos.jsonl
$PY -m pytest -q tests/test_f1_scale.py tests/test_f1_rules.py \
  tests/test_f1_detector.py tests/test_desk_objects.py
```
