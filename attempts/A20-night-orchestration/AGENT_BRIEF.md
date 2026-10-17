# Shared brief (orchestrated task, Datathon 26 cash-discipline checker)

You are one of three implementers working in parallel, each in its own git worktree and branch.
An orchestrator (another agent) will re-run your branch, compare it clip by clip with the others
and merge the best parts. Read AGENTS.md, CONTEXT.md, attempts/README.md (the history of what
was tried) and attempts/A17-leave-rule-fixes/README.md before you start.

## The system

backend/f1/: perception results (per-frame boxes, labels, CLIP states, hand keypoints, track ids)
-> calibration.py (desk/laptop/safe/door zones, cashier/client sides) -> events.py (EventBuilder:
time-ordered events) -> rules.py (one function per rule id, thresholds from config/f1_codex.yaml).
The verdict for a video is "violation" if any finding of a rule enabled in knowledge/rules.yaml
survives.

## How to measure (no GPU needed; the perception cache is already local)

    export API_KEY=x PYTHONPATH=.
    PY=/home/sultanbek/projects/hackathons/dt26-lab/venv/bin/python
    $PY scripts/replay_f1.py run --cache-dir /home/sultanbek/projects/hackathons/dt26-lab/perception_cache > /tmp/<you>.jsonl
    $PY scripts/replay_f1.py score /tmp/<you>.jsonl --labels data/prepared/videos.jsonl
    $PY -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py

Your branch starts from `night`; its baseline is in your assignment.
Per-clip baseline: /home/sultanbek/projects/hackathons/dt26-lab/runs/base.txt. Organizer labels and timestamps: data/prepared/videos.jsonl
(fields original_id, organizer_verdict, organizer_timestamps). The team's own description of
every violation clip (what happens, at which second, which violation): data/Таблица_нарушений.xlsx
sheet "Нарушения" (read it with openpyxl, installed in the venv); clean clips: sheet "Без нарушений".
Each cache entry /home/sultanbek/projects/hackathons/dt26-lab/perception_cache/<sha256>/*.json holds "scene" and "observations"; map
sha256 -> clip name with data/prepared/videos.jsonl.

## Hard rules

- Never open, view or extract video frames or images, and do not try to reach the VM or the
  network. Work only from code, the cached numbers and the spreadsheets.
- Fix mechanisms, not clips: no clip names, hashes or per-clip special cases in code; no threshold
  chosen only because it flips one of these 40 clips. Every change must be explainable as "the
  rule now checks what the norm actually says" or "this signal was being misread", and must make
  sense for unseen videos filmed from another camera angle (the jury scores robustness).
- Stay inside your assigned rules and the code they need. If you must touch shared code
  (events.py, calibration.py, rules.py helpers), keep it minimal and say exactly what and why in
  your report, because the other two agents may touch the same files.
- Do not regress other clips: any clip whose verdict changes for the worse must be listed and
  explained. A change that fixes 2 and breaks 2 is not an improvement.
- Every behaviour change gets a unit test that fails without it. Run ruff
  ($PY -m ruff check / $PY -m ruff format, from the venv) and the tests above.
- Never use the em dash character; use "-". Commit your work on your branch with a plain
  message, no co-author lines. Do not push. Do not edit CHANGELOG or generated files.
- If after honest investigation the cached perception simply does not contain the signal needed
  (e.g. the object is never detected), say so with numbers instead of forcing a rule. A clear
  negative result is a valid outcome.

## Report (your final message, also saved as REPORT-ORCH.md in the worktree root, committed)

1. Score line before/after (the JSON from score).
2. Per target clip: what the cached data shows (numbers, times), what you changed, result.
3. Every other clip whose verdict changed, with the reason.
4. For your rule's hits on violation clips: finding time vs organizer timestamp.
5. Files touched, shared code touched, tests added, what you tried that did not work.
