# A11 - agentB hybrid (F1 detections + VLM probes)

- **Date:** 2026-10-17, ~13:15-13:40 UTC
- **Status:** ran (detection on all videos, VLM probes on dev); **no score recorded**
- **Where it ran:** `datathon`, `~/agentB-hybrid` (`hybrid/detect.py`, `engine.py`, `vlm.py`, `anchors.py`; local copy in `archive/vm-copies/datathon/agentB-hybrid/`)
- **Models:** F1 detection stack plus a Qwen VLM through vLLM

## Approach

Run F1 detection first, then ask the VLM targeted questions only at anchor moments.

## Results

`logs/logs_detect.txt`: detection 4-23 s per video, all 5 scene objects found.
`logs/logs_probe_dev.txt`: 8 dev videos probed, 0 errors, 12-30 s per video. No verdict scores saved.

## Next

Score it with the harness; the anchor idea matches the timecode finding in
`validation/validation-evidence/logs/anchor_probe.txt` (anchors hit 18/22 events at ±1 s vs 13.7 random).
