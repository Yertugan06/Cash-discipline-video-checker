# Owner D2-2: targeted local visual verification, vertical slice

Own new `backend/f1/visual_checks.py`, `backend/f1/detector.py`, `backend/config.py`, optional
`backend/vlm/client.py` changes, new config visual_checks.yaml if needed, and NEW tests scoped to
your module/integration. Do not edit rules.py/events.py/Context, perception.py, knowledge, replay.

Implement bounded event-selected checks for door open/closed, laptop locked/working/closed and
safe open/closed. Use calibrated boxes and F1 events; include scene-start/bootstrap checks when
entry was missed, without falsely treating recording-start presence as an actual entry. No
filename/time lookup. Explicit unknown on missing calibration, occlusion, invalid output or budget
exhaustion. Do not report closed lock state from merely a closed safe door.

There is an existing unfinished `orch/vlmchecks` design in attempts/A20.../tasks/vlmchecks.md;
inspect available code read-only and reuse useful existing architecture. Do not modify another
worktree. Local Qwen3-VL-4B is available on datathon2 under ~/dt26-validation/models; prefer lazy
local model loading with offline-only weights and finite per-video check budget/deadline. If an
already configured loopback local HTTP model service is available, reuse backend/vlm/client.py;
NEVER use external image endpoints. Existing realtime/descriptions.py in annotation preview has
a working Qwen3-VL call path that may inform compatibility. Never change the annotation service.

Return `verify_video(...)` evidence records per shared contract and integrate in F1 detect:
plan -> run -> apply confirmed state observations -> rebuild events -> evaluate. Pass checks as
Context.visual_checks (D3-1 owns optional field). Keep import backend.main light. Trace requests,
answers, failures, provenance and timing. Cache keys must include video/model/prompt/crop and
sampling settings; no stale-answer reuse. Disabled mode must preserve current behavior; enabled
but unavailable means explicit warnings/unknown, not fabricated states. No cash detections or
session ownership generated from a yes/no desk answer.

Prepare a small real state-check runner promptly with gpu-command.json for the orchestrator;
CPU mocked tests alone do not validate the model. One GPU-heavy job per VM. Initial integration
should be opt-in until measured. Target first working CPU vertical slice within35min.
