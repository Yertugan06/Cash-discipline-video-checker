# Your assignment: targeted VLM checks inside F1, branch orch/vlmchecks (from night)

Baseline (night): {"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9}; robust under
--zoom/--mirror/--drop. Read attempts/A20-night-orchestration/LAB.md (decision log, the teammate VLM
comparison) and clip-descriptions.md first.

## Why
CLIP can't read the door, the laptop screen or the safe door (LAB section 5, spike results). The
teammate's prototype (branch local-vlm-prototype, worktree ~/projects/hackathons/dt26-wt/vlm) asks
Qwen3-VL 4B narrow questions on zoomed crops, and on our 40 clips its door and screen answers were
right every time they fired (door: Х-30/32/33; screen: Х-11/28). The user decided: F1 asks the VLM,
**only at moments F1's own events pick**, for: door, laptop screen, safe door, cash on the desk
when a new client sits down (Х-4: previous client's cash left and mixed), and the ID card during a
client session. "Cash without ID" must fire only when the VLM confirmed no ID card was shown (the
teammate found 4B often calls banknotes an ID card, so expect this rule to fire rarely; that is
acceptable: in Х-4 both clients did show their ID, see clip-descriptions.md).

## What to build (one authoritative implementation, no duplicates)
1. `backend/f1/vlm_checks.py`: a pure planner. From the scene and the EventLog it returns check
   requests `{family, t, box (normalised), question_id}`: door a few seconds after an observed
   entry; laptop screen just after a cashier leave; safe door when the cashier walks away from the
   safe or leaves; desk cash when a new client session starts while a previous session existed;
   ID card at a few frames of each client session before the first cash handover. Keep the number
   of requests per clip small (budget: the whole job must stay within 270 s on an L4; Qwen3-VL 4B
   answers a crop in about 0.2-1 s). Boxes come from F1's calibration; say what you do when the
   object isn't calibrated.
2. Questions and JSON answer schemas: reuse the teammate's crop prompts verbatim
   (local-vlm/brev_kit/scripts/zoom_checks.py CHECKS, prototype/pipeline.py ID_Q), stored once in
   the repo (e.g. `config/vlm_checks.yaml` or a prompts file), with their source noted.
3. A VLM call path that reuses `backend/vlm/client.py` (OpenAI-compatible HTTP; Ollama exposes
   /v1 too) instead of a second HTTP client. Add a small generic "ask one image with a JSON schema"
   function there if `ask_frame` is too questionnaire-specific; keep `ask_frame` and its tests
   working.
4. An answer cache, like the perception cache: answers keyed by (video sha256, family, t). Replay:
   `scripts/replay_f1.py vlm-requests` writes every clip's requests as JSONL (sha256, family, t, box,
   question_id) and `run --vlm-answers <file.jsonl>` feeds cached answers to the rules. The
   orchestrator will run the real model on the VM over your request file and give you nothing
   else, so the formats must be documented in the docstring.
5. Rules: A-DOOR-LOCK, L-PC-LOCKED, S-SAFE-CLOSED use the VLM state when an answer exists for the
   relevant moment; C-ID-BEFORE-CASH needs a VLM "no" (and no "yes") on the session's ID checks;
   S-CLEAN-DESK-HANDOVER / S-NO-MERGE may use a VLM "cash on desk = yes" at the new session.
   Without answers (no --vlm-answers, or VLM unavailable in the service) the rules behave exactly
   as night does now, and the service adds an explicit warning; no silent fallback.
6. Service: F1Detector runs the planner after build_events, asks the VLM through the client when
   a setting enables it (e.g. `F1_VLM_CHECKS=1`, `VLM_BASE_URL`, `VLM_MODEL`), respects the job
   deadline, and puts the answers in the trace.

Tests: planner, cache loading, each rule with fake answers (including "no answer" = night
behaviour). With no answers file, the full replay must stay exactly 31/0/9 and every robustness
probe unchanged. Fake answers can show the rules flip the right clips, but don't claim real gains:
the orchestrator measures those with the real model.
