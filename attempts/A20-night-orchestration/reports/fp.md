# Remaining clean false alarms - orch/fp

Baseline: `night` at `12aaf4e`. Only code, cached numbers and workbook text were
inspected. No dataset frames/images, VM or network access, new thresholds, clip
exceptions, model changes or rule enablement changes.

## 1. Scores before and after

Fresh full-data baseline:

```json
{"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9, "outsider_on_clean": 0}
```

All 12 previously caught violation videos stay caught. All 19 clean videos are
correct. Each drop run uses `--drop 0.2 --seed N` over the same 40 videos:

| Seed | Before score JSON | After score JSON |
|---|---|---|
| 0 | `{"videos": 40, "correct": 28, "clean_false_alarm": 2, "missed": 10, "outsider_on_clean": 0}` | `{"videos": 40, "correct": 30, "clean_false_alarm": 0, "missed": 10, "outsider_on_clean": 0}` |
| 1 | `{"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9, "outsider_on_clean": 0}` | `{"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9, "outsider_on_clean": 0}` |
| 2 | `{"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9, "outsider_on_clean": 0}` | `{"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9, "outsider_on_clean": 0}` |

Mean drop accuracy: 28.67 -> 30.67 correct. No verdict regresses against its own
baseline. Seed 0 already missed Х-46 through the unchanged food rule.

## 2. Targets: evidence, mechanism and result

**Х-14:** the clean workbook row says "Вскрытие зелёной сумки и пересчёт сидя за
столом, ноутбук (142 с)." The cache supports continued seated work:

- `person:1` is detected and classified seated in all 285 observations, 0-142 s.
  There are zero cashier EXIT events. Maximum hip distance from the learned
  working position over the whole recording is 0.1516.
- At 62.5 s the hips are `(0.3119, 0.5068)`, only 0.0271 from that learned position,
  but 0.2526 from laptop center, just 0.0026 beyond the existing 0.25 reach limit.
  This starts the old 62.5-66.5 s away interval. Seated confidence is 0.999962.
- Seven confident hand points are inside the calibrated counter at 62.5 s.
  All samples through 65.5 s have counter contact, with 7-27 points inside.

The triggering objects are `cash:119`, 83 detections at 59.5-101.5 s, and
`id_card:38`, 86 at 59.5-102 s. The alleged document is this ID-card label;
`document:1` appears only once at 0 s. At 62.5 s:

| Track | Box | Score |
|---|---|---:|
| `cash:119` | `(0.3570, 0.5053, 0.4001, 0.5272)` | 0.3155 |
| `id_card:38` | `(0.3672, 0.5088, 0.4073, 0.5274)` | 0.3014 |

Their IoU is 0.555; centers vary only about 0.0012 horizontally and 0.0005-0.0006
vertically across their tracks. Neither matches the laptop, counter or any raw
calibration candidate at IoU above 0.01. The separate `tablet:1` matches the laptop
and is already excluded. At 59.5 s the cash/card centers are only 0.0250/0.0288
from the nearest hand. This is an ambiguous tabletop patch near the cashier's
work; the cache cannot identify it exactly or establish two separate objects.
There is no numeric basis for exempting it as a fixture.

The fix addresses the false departure: a confident hand point inside the calibrated
laptop/counter box now confirms workstation presence despite hip distance. Exact
containment adds no proximity threshold. Missing, uncertain and merely nearby
hands do not suppress departures. Confirmed exits retain their behavior.
The 62.5 s interval disappears; the remaining 66 s excursion lasts 0.5 s and fails
the existing two-second item confirmation. Later 117.5/120 s candidates remain
without qualifying items. Result: clean on full data and all drop seeds.

**Х-35:** `coat:1` has 15 detections at 0-7 s. Its initial box is
`(0.3529, 0.5009, 0.6290, 0.5318)`, width 0.2761, height 0.0310. Person overlap is
84.45-86.85%, but relative area is only 15.89-19.24%, below the old 35% worn-coat
requirement. Shoulder midpoint at 0 s is `(0.4914, 0.5217)`, hips `(0.5008, 0.6446)`.
The entire fragment is above the anatomical hip line, with all four torso joints
passing the existing 0.3 confidence threshold. The workbook describes a client
waiting through counting and cash stored at 40-45 s, without item placement.

The coat helper now also recognizes small fragments with the existing >70%
person overlap when reliable shoulder/hip geometry puts the entire box above the
hip line. It uses the shoulder-to-hip direction, not a fixed image axis. Missing,
uncertain, out-of-frame or degenerate pose gives no exemption. All 15 detections
now count as worn. Result: clean on full data and all drop seeds.

**Х-40 guard:** the real desk coat's initial box is
`(0.2066, 0.4316, 0.4574, 0.5009)`, crossing the hips around `y=0.4437`. All nine
`coat:279` worn/not-worn decisions remain unchanged. Findings/durations remain
19.5/4.5 s on full data and seed 0, 19.5/4.0 s on seed 1, and 20.5/3.5 s on seed 2.

## 3. Other changed clips and regressions

Only Х-14 and Х-35 change verdict, both false alarm -> correct, in all four runs.
No other verdict changes and no previously caught violation is lost.

The sole other enabled finding change is Х-15: its early cash-on-leave hit at
10.5 s disappears because confident hand points are inside the laptop during that
away candidate. The 15.0 s hit survives, matching the organizer. The disabled bag
rule has the same change. All other enabled finding lists are identical to their
respective baselines, including Х-40.

## 4. Findings versus organizer times

These are all enabled hits on violation clips in the affected leave/personal
families. PC is included because it also consumes away events. Signed offset is
finding minus organizer. Times are the same on full data and every drop seed,
except Х-40 seed 2.

| Clip / rule | Organizer | After finding | Offset |
|---|---:|---:|---:|
| Х-15 / L-NO-CASH-ON-LEAVE | 15 | 15.0 | 0.0 |
| Х-20 / L-NO-DOCS-ON-LEAVE | 5 | 1.0 | -4.0 |
| Х-24 / L-NO-DOCS-ON-LEAVE | 8 | 8.0 | 0.0 |
| Х-26 / L-NO-CASH-ON-LEAVE | 9 | 12.5 | +3.5 |
| Х-28 / L-PC-LOCKED | 7 | 8.0 | +1.0 |
| Х-40 / W-NO-PERSONAL-ITEMS | 17 | 19.5; seed 2: 20.5 | +2.5; seed 2: +3.5 |

Х-20's workbook describes an open safe, so its unchanged documents hit remains an
incidental verdict match. The disabled bag rule retains Х-15 at 15 s. Clean targets
have no organizer violation timestamps. No global time correction was applied.

## 5. Files, tests, rejected approaches and limitations

- `backend/f1/events.py`: shared code, only the workstation-away branch in `push`.
  Adds exact laptop/counter hand containment as continued-presence evidence.
- `backend/f1/vision_types.py`: shared `worn_or_carried`, used only by personal-item
  events. Extends the coat branch; existing large-coat/handbag behavior is unchanged.
- `tests/test_f1_rules.py`: four new functions, 17 cases. They cover worn fragments
  versus desk coats under original/mirrored/scaled/rotated geometry; unreliable
  pose; event/rule integration; and inside/outside/uncertain/missing hand contacts
  for both equipment types, followed by an actual departure.
- `REPORT-ORCH.md`, `attempts/ORCH-fp-workstation-coat/README.md`, and one row in
  `attempts/README.md`: requested report and attempt history.

Before runtime changes, new tests gave **7 failed, 10 passed**; afterward all 17
pass. Required suites: **151 passed, 1 skipped**, the existing full-model test for
unavailable weights. Required tests use synthetic fixtures; dataset media was never
read. Ruff check, Ruff format and format check pass on all changed Python files;
`git diff --check` passes. Whole-repository Ruff reports 480 existing issues, all
in untouched `attempts/` (66) and `validation/` (414), none in changed code.

The earlier blanket worn-coat overlap filter also suppressed Х-40, according to the
personal-agent report; it was not repeated here. No threshold sweep or unsuccessful
production variant was needed. Static/first-frame item exemptions are unsupported
and were not added. Exact identification of Х-14's cash/card patch remains a
negative perception result, quantified above.

Nine full-data misses remain: Х-17, Х-33, X-1, Х-44, X-2, Х-13, Х-11, Х-32 and Х-22.
Incorrect pose or projected hand/equipment overlap can still mislead geometry.
Drop tests do not simulate lost person keypoints or prove new-camera performance.
No model/GPU rerun, deployment or push was performed; no generated files changed.

Local evidence: `/tmp/fp-evidence.txt`, `/tmp/fp_inspect.py`,
`/tmp/fp-{before,after}{,-drop0,-drop1,-drop2}.{jsonl,txt}`, `/tmp/fp-red.txt`,
`/tmp/fp-ruff-all.json`. Reproduction is in the attempt README.
