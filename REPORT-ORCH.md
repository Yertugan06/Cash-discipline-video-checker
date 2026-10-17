# Scale invariance report - orch/scale

1. Score before and after

Starting revision: `c723ff6` (night baseline). Replayed all 40 cached videos using the
local venv and organizer labels. Each `before`/`after` object below is the actual final
JSON line from `scripts/replay_f1.py score`.

```jsonl
{"probe":"full","before":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"zoom 0.8","before":{"videos":40,"correct":28,"clean_false_alarm":1,"missed":11,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"zoom 0.9","before":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"zoom 1.1","before":{"videos":40,"correct":28,"clean_false_alarm":2,"missed":10,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"zoom 1.2","before":{"videos":40,"correct":29,"clean_false_alarm":0,"missed":11,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"mirror","before":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"drop 0.2 seed 0","before":{"videos":40,"correct":30,"clean_false_alarm":0,"missed":10,"outsider_on_clean":0},"after":{"videos":40,"correct":30,"clean_false_alarm":0,"missed":10,"outsider_on_clean":0}}
{"probe":"drop 0.2 seed 1","before":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
{"probe":"drop 0.2 seed 2","before":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0},"after":{"videos":40,"correct":31,"clean_false_alarm":0,"missed":9,"outsider_on_clean":0}}
```

Full-data findings are identical to the original run, including rule IDs and times.
Every requested zoom and mirror now produces that same list on all 40 clips.
Each drop run is also identical to its original counterpart. Seed 0 still misses
the food finding on Х-46; that was already the case before this change.

The only normalization is `old_distance * max(desk_width, desk_height) / 0.70`.
Before changing code, the measured desk span across the cache was min/median/max
0.5803/0.7072/0.7522. Laptop spans varied 0.1148-0.2169 and median cashier heights
0.1270-0.2455, so the desk was the more consistent reference here. The common 0.70
reference was chosen from scene geometry before replaying the fix; it was never
adjusted per clip or to select a verdict. A scene without a calibrated desk explicitly
retains the old distances because its scale is unknown.

2. Per-target cached evidence, mechanism, and result

All distances below are normalized image distances in the original cache unless a zoom
is specified. Clip aliases share one checksum and count once in the 40-video score.

| Clip | Cached evidence and previous zoom behavior | Change and final result |
|---|---|---|
| Х-20 | At 1 s, hip-to-laptop distance is 0.3039. At zoom 0.8 it becomes 0.2431, falsely qualifying as within the old 0.25 reach. Only three unzoomed lone frames at 4/4.5/5 s qualify by hips; their median anchor is (0.3346, 0.3940). At zoom 1.2 only one hip frame meets the old reach, switching to hand-based calibration. Both zooms lose the finding. | Scale calibration reach, anchor selection, and away distance together. The original `L-NO-DOCS-ON-LEAVE@1.0` is preserved at every zoom. This remains a semantically wrong hit: the workbook labels an open safe at 5 s. It is a preserved baseline verdict, not a repaired safe detector. |
| Х-38 | Cash appears at 27 s. At 31.5 s the closest hand is 0.0703 away; at zoom 0.8 it is 0.0562, inside the old 0.07 hand threshold. Cash then stays classified as held through the second session at 32 s, suppressing desk handover. | Scale object ownership and desk-item hand margins. The corrected zoom-0.8 hand threshold is about 0.0533. `S-CLEAN-DESK-HANDOVER@32.0` survives every zoom. At zoom 0.9 this also replaces spurious leave findings at 28 s with the baseline handover finding. |
| Х-5 / Х-48, clean | Around 35/35.5/36 s, person:11's box ends 0.0245/0.0305/0.0367 above the desk. Zoom 0.8 shrinks these to 0.0196/0.0244/0.0294, all inside the old 0.03 glass clearance. That admits an extra apparent client long enough to emit `A-SECOND-PERSON@35`. | Scale glass clearance and service proximity. At zoom 0.8 the glass clearance is about 0.0250, so the 36 s sample is excluded and the apparent service overlap cannot sustain the finding. Clean at all zooms. |
| Х-34 | During lone frames at 0/0.5/1/2 s, nearest hands need laptop margins 0.0703/0.0693/0.0682/0.0628. At zoom 1.2 they need 0.0843/0.0832/0.0818/0.0753. Only one fits the old 0.08, fewer than the three frames needed to calibrate the cashier. | Scale laptop hand margin and desk selection. The corrected desk span is 0.6305 at zoom 1 and 0.7566 at 1.2, giving a 1.2 hand margin of 0.0865 and four usable frames. `C-COUNT-BEFORE-EXIT@15.0` survives every zoom; the counter starts at 13 s. |
| Х-10, clean | At zoom 1.1 the old reach produces an away interval 1-4 s and cash/docs findings at 1 s, although there is no away interval in the unzoomed run. The learned anchor-to-laptop gap changes from 0.2276 to 0.2469 instead of the geometric 0.2504. | Use the same scene-relative reach during learning and away detection. At zoom 1.1 the reach is 0.2805. No away interval or finding remains. Clean at all zooms. |
| Х-8, clean | Zoom 1.1 creates docs findings at 1.5, 10.5, and 22 s; away intervals include 1.5-4 and 10.5-19.5 s. Its desk span is 0.7406, so a fixed 0.25 reach shrinks relative to the workstation as zoom grows. | Scale reach and desk-item proximity consistently. At zoom 1.1 reach is 0.29095. The sole final away interval is 28.5-30.5 s at every zoom and produces no finding. Clean throughout. |
| Х-15 | The leave finding shifts from 15 s to 17 s at zoom 0.8 and 13.5 s at 1.1/1.2. | Scene-relative workstation reach and item checks restore `L-NO-CASH-ON-LEAVE@15.0` at every zoom. |
| Х-18 | Second-person service shifts from 19.5 s to 18 s at zoom 0.8. | Scale glass and desk-hand service margins. Restore `A-SECOND-PERSON@19.5` at every zoom. |
| Х-24 | Docs-left time is 8 s unzoomed, 8.5 s at 0.8, 6/10.5 s at 1.1, and 10.5 s at 1.2. | Scale workstation reach and desk-item checks. Restore only `L-NO-DOCS-ON-LEAVE@8.0` at every zoom. |
| Х-26 | Cash-left time is 12.5 s unzoomed, 13 s at 0.8/0.9, 11 s at 1.1, and 10.5/15 s at 1.2. | Scale the same workstation/item geometry. Restore only `L-NO-CASH-ON-LEAVE@12.5` at every zoom. The baseline timestamp remains 3.5 s late. |
| Х-46 | Original food findings are 12/15.5 s. Zoom 0.8 adds 13/18 s, 0.9 adds 13 s, and 1.1/1.2 lose 12 s. | Scale head, hand, and desk proximity together. Restore exactly 12/15.5 s at every zoom. |
| Х-4 / Х-47 | The ID-before-cash finding changes from 66 s to 63.5 s at zoom 1.1/1.2. | Scale object-hand ownership. Restore `C-ID-BEFORE-CASH@66.0` at every zoom. The workbook labels previous-client cash/mixing; the baseline rule identity remains a limitation. |
| Х-14, clean, intermediate failure | The old laptop-on-desk margin selects a desk spanning 0.7509 unzoomed but small boxes spanning 0.1914/0.2088 at zoom 1.1/1.2. The laptop center is about 0.0186 above the true desk edge unzoomed, crossing the fixed 0.02 tolerance when enlarged. | Scaling downstream distances alone turns the small desk into a bad reference and falsely flags `W-NO-PERSONAL-ITEMS@31`. Scaling the candidate desk containment margin before clustering fixes this. Final desk spans are 0.7513/0.8265/0.9016 at zoom 1/1.1/1.2. The trial false alarm is absent in the final code. |

3. Other verdict changes and frame-border effects

There are no worse verdicts in any of the nine requested comparisons.

| Probe | Verdict changes compared with the same probe before the fix |
|---|---|
| Full | None, all 40 unchanged |
| Zoom 0.8 | Х-20 and Х-38 recovered; Х-5/Х-48 false alarm removed |
| Zoom 0.9 | None; finding types/times return to baseline |
| Zoom 1.1 | Х-20 recovered; clean Х-8 and Х-10 false alarms removed |
| Zoom 1.2 | Х-20 and Х-34 recovered |
| Mirror; drop seeds 0/1/2 | None |

The 0.12 entry-border and 0.18 exit-border tests remain fractions of the actual image.
The [0, 1] visibility checks for pose points also remain unchanged. An actual image
edge does not shrink with a desk: for example a point 0.05 from an edge moves to 0.14
at zoom 0.8, so a border test may legitimately change. Door proximity and movement
away from the desk describe scene geometry and now scale instead. In the final runs,
all ENTER observed-entry flags and EXIT/TRACK_LOST event identities/times agree with
the unzoomed final run for all 40 clips at all four zooms. No residual verdict change
needs a border exception here. The raw cached detections are not clipped by the probe.

4. Finding times versus organizer timestamps

These are the final full-data hits, unchanged at every requested zoom and mirror.
Delta is finding time minus organizer time. Equal verdicts do not establish that
the finding describes the labeled action, particularly the marked baseline mismatches.

| Clip | Rule | Finding s | Organizer s | Delta s |
|---|---|---:|---:|---:|
| Х-30 | A-OUTSIDER-ZONE | 13.0 | 13 | 0 |
| Х-47, alias Х-4 | C-ID-BEFORE-CASH | 66.0 | 68, alias 57 | -2, alias +9 |
| Х-38 | S-CLEAN-DESK-HANDOVER | 32.0 | 33 | -1 |
| Х-46 | W-NO-FOOD | 12.0, 15.5 | 11 | +1, +4.5 |
| Х-15 | L-NO-CASH-ON-LEAVE | 15.0 | 15 | 0 |
| Х-40 | W-NO-PERSONAL-ITEMS | 19.5 | 17 | +2.5 |
| Х-20 | L-NO-DOCS-ON-LEAVE | 1.0 | 5 | -4; labeled action is open safe |
| Х-18 | A-SECOND-PERSON | 19.5 | 20 | -0.5 |
| Х-24 | L-NO-DOCS-ON-LEAVE | 8.0 | 8 | 0 |
| Х-28 | L-PC-LOCKED | 8.0 | 7 | +1 |
| Х-26 | L-NO-CASH-ON-LEAVE | 12.5 | 9 | +3.5 |
| Х-34 | C-COUNT-BEFORE-EXIT | 15.0 | 13 | +2 |

5. Files, shared contracts, validation, and limitations

- `backend/f1/vision_types.py`: one `desk_scale` function and `Scene.scaled_distance`,
  using the desk's long side, including a documented unknown-scale behavior. No
  serialized fields, cache format, labels, or per-clip data added.
- `backend/f1/calibration.py` (shared): scale the laptop-on-candidate-desk margin
  before selecting a desk; use scene-relative glass, laptop hip/hand, and zone margins.
  `in_zone` now scales its margin internally. Callers must pass reference distances
  once; do not scale them again at the call site.
- `backend/f1/events.py` (shared): convert existing physical distances for ownership,
  fixtures/bags, cashier assignment/absence, collector carrying, cash reassociation,
  confirmed motion away, safe attendance, fixture contact, and food proximity.
  `MoneyFlow` accepts an optional reassociation distance; its existing default and
  standalone calls remain compatible. Temporal thresholds and actual image-border
  checks are unchanged. `contains` still takes image distances, so its callers use
  `Scene.scaled_distance` explicitly.
- `backend/f1/rules.py` (shared): only `Context.items_on_desk` changes, scaling the
  existing 0.01 fixture and 0.045 wrist exclusions. Rule bodies are unchanged.
- `config/perception.yaml`: a comment documenting reference-distance units; no values
  changed. `person_min_height` is a detector-stage filter and is not exercised by a
  coordinate-only cache replay, so it was not changed.
- `tests/test_f1_scale.py`: 15 test functions, 277 synthetic cases over zoom 0.8/1/1.2
  and wide/tall desk orientations. Both sides of each proximity cutoff are covered,
  including calibration, role/leave timing, glass/service, cash ownership/reassociation,
  bag inspection/carrying, left items, attendance/contacts, food, and departure motion.
  Against the original four implementation files, 95 cases fail, spanning all 15
  functions; with the fix all 277 pass.
- `tests/test_f1_rules.py`: keep the existing closer-client test inside the newly
  scene-relative reach. Its desk span is 0.66, so reach is now 0.2357; the old fixture's
  hip gap 0.2421 was outside it. Moving its cashier from (0.4, 0.62) to (0.39, 0.61)
  keeps the original assertion meaningful without changing production thresholds.
- `REPORT-ORCH.md`, `attempts/README.md`, and
  `attempts/A21-scale-invariance/README.md`: report and attempt index.

Executed with `/home/sultanbek/projects/hackathons/dt26-lab/venv/bin/python`:

```text
pytest -q tests/test_f1_scale.py tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
428 passed, 1 skipped

ruff check backend/f1/calibration.py backend/f1/events.py backend/f1/rules.py backend/f1/vision_types.py tests/test_f1_scale.py tests/test_f1_rules.py
All checks passed!

ruff format backend/f1/calibration.py backend/f1/events.py backend/f1/rules.py backend/f1/vision_types.py tests/test_f1_scale.py tests/test_f1_rules.py
ruff format --check on those same six files
6 files already formatted
```

The skipped test is the existing model-backed `test_detect_runs_end_to_end`. Root
`ruff check` also ran: 480 existing errors (414 under `validation`, 66 under `attempts`).
Restoring the original implementation files yields the same 480 findings; the final
finding multiset matches exactly. Those unrelated historical scripts were left alone.

The unsuccessful intermediate approach scaled event/rule geometry while leaving the
0.02 calibration margin fixed. It scored 31/31/31/30/30 for full/zoom 0.8/0.9/1.1/1.2,
with a new clean Х-14 false alarm at the two higher zooms. That approach was rejected;
fixing the earlier calibration margin removed the regression without changing the
0.70 reference or adding a rule exception.

No dataset videos, frames, or images were opened, viewed, or extracted, and no network
or VM was used. Measurements came from cached coordinates, code, and the workbook.
No generated replay files are committed; local run artifacts are under
`/tmp/scale-before*` and `/tmp/scale-second*`. The workbook was read with openpyxl,
including both requested sheets.

Limitations: the nine original misses and baseline rule/action mismatches remain.
This validates rule geometry under coordinate transforms, not perception accuracy at
a new camera distance or perspective. A missing or incorrectly calibrated desk still
limits the scale estimate. GPU inference and deployment were not run.
