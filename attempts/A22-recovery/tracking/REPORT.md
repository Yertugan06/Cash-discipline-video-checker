# A22 temporal cash tracking — CPU diagnostic

No rule gain and no supported previous-session cash recovery. The prototype remains opt-in;
no production caller, detector, rule, service, dependency or configuration was changed.

Actual scope: new backend/f1/temporal_refinement.py; one small synthetic test file;
tracking/run_probe.py plus frozen matcher limits, exact argv and numerical reports.
The replay imported events/rules/calibration from shared/a22/base (requested main
5fae84bc10415111a04b5982d156727ca80f788a), as recorded in run metadata and summary hashes.
The worker's older A21 modules were not used by the replay.

API: refine_cash_tracks(frames, scene, observations, deadline) returns deep-copied
observations and provenance. Original NN samples are retained byte-for-value. New boxes
retain their source track ID, NN label and earliest-seed NN confidence; NCC/cycle quality
are separate provenance fields. The matcher never assigns an owner/session or emits a
handover. Call it once on original NN observations; Detection has no per-sample source tag.

Frozen before real matcher outputs at 04:27 UTC: NCC >= .90; <=8 s backward;
two consecutive 2-fps NN seeds; patch std >=12 gray levels; minimum side 6 px;
peak gap >=.05; seed size ratio <=1.25; two-seed center agreement and forward/back
cycle error <=2 px; search radius .04 times image short side (minimum 4 px).
Only the earliest two seeds per track are used. Any overlap with a different visible
track blocks a seed/new sample. First failed/ambiguous/occluded frame stops backtracking;
it never resumes across that gap. No threshold or anchor was adjusted from clip outcomes.

| Focused input | New samples | Existing findings changed | Stop reasons |
| --- | ---: | --- | --- |
| X4 | 1 | no | {'low_ncc_or_occlusion': 1} |
| X5 | 0 | no | {} |
| X26 | 0 | no | {'seed_collision': 1} |
| X27 | 0 | no | {'two_consecutive_nn_seeds_required': 1} |
| X38 | 0 | no | {'seed_collision': 3, 'two_consecutive_nn_seeds_required': 1} |
| X39 | 0 | no | {'two_consecutive_nn_seeds_required': 1} |

All 40 unique inputs (X4/X47 and X5/X48 are duplicate files):

- 4 new appearance-supported samples; all existing findings unchanged.
- All HANDOVER event lists unchanged. No new ID/document accusation or shifted rule anchor.
- Canonical CPU decode + matching + both rule replays: 52.329 s total.
- Rejections/stops: {'low_ncc_or_occlusion': 2, 'no_earlier_frame': 1, 'two_consecutive_nn_seeds_required': 9, 'seed_collision': 10}.

| Input | Genuine seed times | New times | Minimum NCC | Maximum cycle error px |
| --- | --- | --- | ---: | ---: |
| X4 | [(57.0, 57.5)] | [56.5] | 0.980045 | 0.000 |
| X13 | [(23.5, 24.0)] | [22.0, 22.5, 23.0] | 0.953229 | 0.000 |

X4: source seeds are at57 and57.5 s. The only supported backtrack is56.5 s
(NCC .993280/.980045, cycle error0 px; raw NN score .381219536 is preserved).
The next past frame56.0 s fails the frozen NCC threshold. Session2 already begins55.5 s
and previous client exit is53 s in the existing event history. This does not establish
old cash before session2, so provenance is not reassigned and the missed mechanism remains.

X38 existing supported findings remain. X5/X48 and X39 add no cash samples; X26/X27
add none. No result is inferred from clip identity or human/organizer outcome.

Checks actually run:

- RULE_SCOPE=detector .venv/bin/pytest -q tests/test_temporal_refinement.py: 7 passed in0.33 s.
  One parametrized test covers movement, occlusion, ambiguous duplicate background,
  another visible track, a single seed, flat texture and expired deadline; it also
  checks original NN preservation and raw-score/NCC separation.
- Ruff check/format on the three new Python files and git diff --check: passed.
- Real six-input CPU replay and the inexpensive full40 CPU replay completed.
- No current test failures. No GPU execution or broad test suite was run.

Run exactly with cpu-command.json (focused) or cpu-all40-command.json. Example:

```bash
.venv/bin/python -c 'import json,subprocess; from pathlib import Path; argv=json.loads(Path("attempts/A22-recovery/tracking/cpu-command.json").read_text()); raise SystemExit(subprocess.run(argv).returncode)'
```

Inputs are canonical frames produced by the existing A22 F1Detector._extract_frames
at2 fps. They live only in temporary VM directories and are removed after each clip.
Only numeric/text evidence is saved; no frames, pixels, base64 or credentials are exported.

These are development replays: all40 public inputs influenced prior development.
This is not held-out accuracy. The replay compares CV-only Contexts without invoking
the production second-stage verifier, and is not a replacement measurement for the
reported live30/40 baseline. Base rules/ID applicability are unchanged.

Limits: correlation can reproduce a mistaken NN cash label or background inside its
box. Conservative collision/occlusion checks limit recall; single/invalid early seeds
are not supplemented with later favorable seeds. There is no cross-ID merge or
occlusion bridging. The source API assumes raw NN input observations.

Skipped: production integration, GPU/LLM inference and further matcher variants.
Risk: the target prior-cash history is still unsupported. No tracking-based ownership
or rule promotion is justified by these four added samples.
