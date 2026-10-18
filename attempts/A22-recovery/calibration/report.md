# A22 D2-2 — fixture context evidence

Candidate base: combined shared `a22/base`, commit
`5fae84bc10415111a04b5982d156727ca80f788a`. Only new owned files are packaged;
the older dirty A21 implementation is excluded. No existing events/rules, service,
dependencies, global config or annotations were changed. No GPU, decoding, neural
inference, image viewing or cloud pixel tools were used.

## Delivered API

`backend/f1/fixture_evidence.py`: `fixture_evidence(scene, observations) -> list[dict]`.
Each exact timestamp contains fixture boxes/model scores/candidate support/overlap,
people boxes/roles, body wrist 9/10 coordinates/confidence/reliability, adjacent
same-track wrist displacement, posture, counter/laptop states, geometric box gaps,
exact wrist-box inclusion, overlapping-fixture ambiguity, and missing-hand uncertainty.
All scores and roles retain input provenance. No new cashier identification is made.

`exclusive_box_projection` means only a reliable wrist point lies inside one of
the calibrated 2D boxes. It is **not** physical handling or attendance. Legacy
expanded proximity and all-hand-landmark counts are reported separately. Missing
wrists give `unknown`; seated posture never decides attendance. The module does
not infer locks, departures, ownership or violations, and does not propagate facts
between samples. Classifier states are raw cached model outputs, not human truth.

Geometry was frozen before corpus diagnostics: wrist confidence >=0.5, normalized
points inside the person box, exact fixture inclusion with no margin, candidate
support IoU >0.3 (base calibration vote), and motion only for gaps <=0.75 s. Numeric
box gaps/motion introduce no action threshold. Thresholds were not retuned on clips.

## Measured numeric findings

All **40** cache entries were recalibrated and assigned roles with the shared base
helpers, then processed in **4.09 s**: **2,601 samples**, 4,633 person samples,
**2,082 cashier samples**. The extractor reproduces the base legacy geometry with
**0 mismatches**. Video names are diagnostic hash mappings only, never features.

- Legacy safe attendance is true in **680** cashier samples. **400** lack a reliable
  body wrist inside the exact safe box; **286** have both reliable wrists outside.
  These are support discrepancies, **not** 400 proven attendance mistakes.
- Exact safe wrist projection appears in 280 samples: 243 exclusive to the safe
  among these fixture boxes and 37 ambiguous with another fixture. **969** cashier
  samples have unknown safe wrist support. **207** confident body wrist points
  across all people lie outside their person box and are excluded as reliable.
- Safe/laptop boxes overlap in **23/40** clips. Exact safe/counter overlap occurs
  in 5; adding the legacy hand margin produces counter overlap in **19/40**.
- Of legacy-attended samples, 634 are classified seated and 90 have the counter
  classified running. Neither fact alone proves another action or unattended safe.

X20/X21 recalibrated safe boxes match the supplied geometry, about
(.394,.285,.59,.436); safe/laptop IoUs are .232/.237. Both safe boxes have 3 of 6
same-label calibration candidates supporting the selected box. At X20 7/7.5 s,
both reliable wrists are outside the safe, the counter is classified running, and
the right wrist's counter-box gaps are .00168/.00338 reference units versus
.06440/.06126 to the safe. At 8/8.5 s the left wrist projects just inside the safe
again while the counter still runs. Thus direct box inclusion alone also cannot
resolve physical handling in this projection; no binary correction is shipped.

Requested controls, using the frozen extractor (counts are descriptive):

| Clip | Cashier samples | Legacy near | Exact safe wrist | Unknown wrist support |
|---|---:|---:|---:|---:|
| X20 | 21 | 19 | 8 | 3 |
| X21 | 37 | 37 | 14 | 4 |
| X5 / byte-identical X48 | 141 | 21 | 10 | 114 |
| X8 | 74 | 31 | 0 | 7 |
| X14 | 279 | 0 | 0 | 43 |
| X19 | 113 | 13 | 8 | 89 |
| X27 | 46 | 36 | 23 | 21 |
| X39 | 0 | unavailable | unavailable | no assigned cashier |

The base also assigns no cashier in X35. Those clips still have per-person facts;
missing role evidence must not become a negative attendance fact. Clean controls
also show proximity without direct support, so substituting a new unattended rule
would be unjustified. All 40 public clips influenced development; there is **no
held-out accuracy or detector-score improvement claim**. The supplied 30/40
baseline was not rescored because no existing rule behavior was changed.

## Validation / reproduction

Tests ran against a fresh copy of the **combined A22 base** under
`/tmp/a22-fixture-d2-2-g4ru_v1b`, overlaying only the new module/test:

```text
/home/ubuntu/workspaces/datathon26-workers/worker-2/.venv/bin/python -m pytest -q tests/test_fixture_evidence.py
3 passed in 0.04s
```

Cases cover overlapping fixtures with competing counter contact, 42 fingertip
landmarks with missing/invalid wrists, and same-track motion versus a visibility
gap. JSON serialization rejects nonfinite output. Ruff check/format checks pass.
Initial test fixture used NaN, which the existing Detection model rejects before
the extractor; it was corrected to a finite out-of-frame wrist. No final failures.
No broad tests were run.

Exact CPU diagnostic cwd/env/argv: `cpu-command.json`; output `diagnostics.log`.
`numeric/summary.json` contains all-40 aggregates and per-clip calibration/support
counts; `numeric/cashier_samples.csv` contains exact cashier timelines and raw
wrists; `numeric/<video_sha256>.jsonl.gz` contains every sample for the LLM worker.
Only text/numbers are included, never frames. The runner imports base calibration,
role assignment and vision types, and explicitly loads the owned candidate module.

`fixture-evidence-new-files.tar.gz` is a new-file-only archive relative to the
candidate repository root. Integrate the module into the LLM context owner only
after review; it is intentionally not wired into policy/rule evaluation here.

Remaining limit: 2D pose/calibration and cached classifier states cannot establish
physical contact or active handling. Missing/occluded hands, overlapping projection
and uncertain roles remain explicit. No real improvement in final verdict accuracy
has been validated, and no new GPU run is required for this numeric prototype.
