# A22 D2-2 fixture evidence — in progress

Start 2026-10-18 04:26 UTC. Candidate base is shared `a22/base`, committed
`5fae84bc10415111a04b5982d156727ca80f788a`; the old dirty A21 tree is not the base.
Own only this directory, new `backend/f1/fixture_evidence.py`, and new
`tests/test_fixture_evidence.py`. No existing rule/event/service/config edits.

API: `fixture_evidence(scene, observations)` returns JSON-safe exact-sample neutral
fixture/pose facts for the LLM context worker. A 2D near/contact is not attendance
or handling. Missing/occluded hands produce unknown, never absence or room exit.

Geometry frozen before corpus diagnostics / labels:

- Primary wrists are COCO body keypoints 9/10, minimum confidence 0.5, normalized
  and within the detected person box. Every hand fingertip is **not** a wrist.
- Actual fixture contact uses its exact normalized box, no expansion. A point
  inside multiple fixture boxes is ambiguous projection, not exclusive handling.
- Legacy proximity is reported separately using the existing 0.08 person-center
  and 0.05 any-landmark margins, scaled by the calibrated desk as in the base.
- Consecutive same-track wrist motion uses gaps <=0.75 s and reports numeric
  displacement. Contact+motion is a support fact, never a business conclusion.
- Calibration candidate support uses the existing calibration IoU >0.3 vote.
- No posture-only unattended rule, layout/filename/time/clothing/annotation logic,
  threshold retuning, inference, GPU job, image viewing or cloud pixel tools.

The shared cache contains 40 directories. Will inspect all with frozen settings,
report overlaps/legacy-contact mismatches, and compare the requested clean controls
descriptively. No held-out claim or detector score improvement will be made.

04:32 UTC handoff: all 40 entries processed; final **3 tests passed in 0.04s**
against a combined-base overlay, Ruff checks passed. Detailed findings/limitations
in `report.md`; exact run argv in `cpu-command.json`; full numeric evidence in
`numeric/`. New-file-only archive `fixture-evidence-new-files.tar.gz` excludes all
old dirty A21 files and existing production sources. Ready for orchestrator review;
no attendance policy or verdict improvement claimed.
