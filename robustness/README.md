# Robustness: other-angle filming protocol

Criterion 5 of task.md §9 ("устойчивость", 10 points) scores "работа на
ранее не показанных видео, в том числе снятых под другим углом". The
training dataset and development runs all use one fixed top-down angle, one
camera, one desk (task.md FAQ 3); the jury's final test video is filmed
from a different angle (task.md FAQ 4). This protocol produces this team's
own other-angle evidence before that happens
(`reasearch1/implementation-plan.md` WP4).

## Why self-filmed clips, and how they are used

Self-filmed clips are a robustness **check**, not a training or tuning set:
do not adjust rule thresholds to fit them after the dev-set config is
frozen (`reasearch1/implementation-plan.md` Phase 3 pre-registration,
"no lockbox look before freezing on dev" — the same discipline applies
here). They only tell us whether the service still runs and still finds
the right kind of thing from an angle it has never seen.

## Filming protocol

- **Equipment:** 2 phones, placed at a **different angle** from the training
  dataset's top-down, single-camera view (e.g. a corner/eye-level angle
  instead of overhead) — different angle per phone is fine and increases
  coverage.
- **Count:** 10–20 short clips total (comparable length to the training
  clips, 10–145 s; task.md FAQ 1).
- **Content:** matched **violation / clean pairs** for each of the top
  mechanisms below, so every violation clip has a same-setup clean
  counterpart:
  1. **Cash left on the desk** (`L-NO-CASH-ON-LEAVE`) — cashier steps away
     with cash visible vs. cashier steps away with the desk clear.
  2. **Door** (`A-DOOR-LOCK`) — someone enters without closing the door vs.
     the door closed promptly.
  3. **Keys** (`L-SAFE-LOCKED-ON-LEAVE`) — key left in the safe lock on
     leaving vs. key removed/safe locked.
  4. **Unlocked screen** (`L-PC-LOCKED`) — workstation left unlocked on
     leaving vs. screen locked before leaving.
- **Consent/privacy:** only team members or consenting volunteers appear on
  camera; no real documents, real cash or real card numbers are shown. No
  faces need to be hidden (the service does no face recognition,
  `docs/MODELS.md`), but prefer camera framing that is consistent with the
  training setup's intent (a desk/booth scene) over close facial shots.

## Naming convention

```
robustness/clips/<angle>-<mechanism>-<pair>-<violation|clean>.mov
```

- `<angle>`: a short tag for the camera position, e.g. `corner1`, `eye2`
  (not `top` — that is the training angle, out of scope for this check).
- `<mechanism>`: one of `cash`, `door`, `keys`, `screen`.
- `<pair>`: a two-digit index per mechanism, e.g. `01`, `02`, matching the
  violation clip to its clean counterpart.
- Example pair: `corner1-cash-01-violation.mov` / `corner1-cash-01-clean.mov`.

Clips are **never committed to this repository** (SHARED_BRIEF.md,
`implementation-plan.md` WP4: "Clips are never committed") — keep them in
`robustness/clips/` locally. As of this writing the root `.gitignore` does
not yet exclude `robustness/clips/` or `*.mov` (that file is outside
WP4's file set, see this doc's authoring report) — **add that ignore rule
before filming**, and in the meantime double-check `git status` before any
commit to make sure no clip is staged.

## Running the clips through the service

Use the external acceptance suite (`tests/e2e/`), pointed at the real,
public deployment and this clip directory — the same path a jury member
would take:

```bash
E2E_BASE_URL=https://TODO-team-host.example \
E2E_API_KEY=<key> \
E2E_CLIPS_DIR=robustness/clips \
.venv/bin/python -m pytest tests/e2e -v
```

This uploads every `.mov` clip in the directory through the public API,
polls each job, asserts it reaches `done` in under 300 s, validates the
response against `backend.contracts.DoneJob`, and checks every evidence
frame decodes as a real JPEG. It prints only each clip's filename, verdict,
violation count, runtime and coverage mode — never the clip's content
(privacy rule, SHARED_BRIEF.md).

For a by-eye review of whether the *right* mechanism fired (not just that
the job completed), open each clip's result in the UI's demo/manual flow
and compare the reported violation type against the clip's filename.

## Results table (fill in after the run)

Report the result honestly, however it comes out — "tested on N self-filmed
clips, X/Y" if the run completed, or **"untested on other angles"** if time
ran out before filming/running this check
(`reasearch1/implementation-plan.md` WP4: "If time runs out, state
'untested on other angles'"). Do not round up, do not omit a clip that
failed or errored.

| Mechanism | Pair | Angle | Clip | Expected | API verdict | Runtime (s) | Correct type? | Notes |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| Cash on desk | 01 | TODO | `corner1-cash-01-violation.mov` | violation | TODO(team) | TODO(team) | TODO(team) | |
| Cash on desk | 01 | TODO | `corner1-cash-01-clean.mov` | no_violation | TODO(team) | TODO(team) | n/a | |
| Door | 01 | TODO | | violation | | | | |
| Door | 01 | TODO | | no_violation | | | | |
| Keys | 01 | TODO | | violation | | | | |
| Keys | 01 | TODO | | no_violation | | | | |
| Screen | 01 | TODO | | violation | | | | |
| Screen | 01 | TODO | | no_violation | | | | |

**Summary:** TODO(team) — e.g. "tested on N self-filmed clips, X/Y verdicts
correct, Y/Y finished under the time budget" or "untested on other angles".

This summary line is also the one that belongs in `docs/LIMITATIONS.md`
("Camera angle" section) and in the G4 checklist (item 5,
`reasearch1/implementation-plan.md` §4) — keep the two in sync.
