Timecode and evidence-anchor audit on `orch/timecode`, starting at `12aaf4e` (`night`).
Only cached numbers, code and the two workbook sheets were read. No network, VM, video or image access was used.

1. Verdict scores and timing before/after

Full-cache score before:

```json
{"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9, "outsider_on_clean": 0}
```

Full-cache score after:

```json
{"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9, "outsider_on_clean": 0}
```

Every verdict is identical across all 160 paired results. The complete raw `(rule_id, t)` lists are also identical. Only the order of the two findings in Х-15 changes, in all four runs. `K-SEAL-CHECK` has no hits in these runs, so its anchor correction has no measured timing benefit here.

| Replay | Score JSON before = after |
| --- | --- |
| Full | `{"videos":40,"correct":29,"clean_false_alarm":2,"missed":9,"outsider_on_clean":0}` |
| Drop 0.2, seed 0 | `{"videos":40,"correct":28,"clean_false_alarm":2,"missed":10,"outsider_on_clean":0}` |
| Drop 0.2, seed 1 | `{"videos":40,"correct":29,"clean_false_alarm":2,"missed":9,"outsider_on_clean":0}` |
| Drop 0.2, seed 2 | `{"videos":40,"correct":29,"clean_false_alarm":2,"missed":9,"outsider_on_clean":0}` |

Timing is conditional on caught violation clips, not recall over all violations. Each cell shows before -> after; tolerance counts are inclusive. Top-1 uses the actual service adapter, ranking and cap of 3. Best uses every raw finding, with one vote per unique clip.

| Replay / selection | Caught clips | Mean absolute offset, s | Within ±1 s | Within ±2 s | Within ±3 s | Within ±5 s |
| --- | ---: | --- | --- | --- | --- | --- |
| Full / best | 12 | 1.458 -> 1.458 | 7 -> 7 | 9 -> 9 | 10 -> 10 | 12 -> 12 |
| Full / top-1 | 12 | 1.833 -> 1.458 | 6 -> 7 | 8 -> 9 | 9 -> 10 | 12 -> 12 |
| Drop seed 0 / best | 11 | 1.500 -> 1.500 | 6 -> 6 | 8 -> 8 | 9 -> 9 | 11 -> 11 |
| Drop seed 0 / top-1 | 11 | 1.909 -> 1.500 | 5 -> 6 | 7 -> 8 | 8 -> 9 | 11 -> 11 |
| Drop seed 1 / best | 12 | 1.458 -> 1.458 | 7 -> 7 | 9 -> 9 | 10 -> 10 | 12 -> 12 |
| Drop seed 1 / top-1 | 12 | 1.833 -> 1.458 | 6 -> 7 | 8 -> 9 | 9 -> 10 | 12 -> 12 |
| Drop seed 2 / best | 12 | 1.792 -> 1.792 | 6 -> 6 | 8 -> 8 | 8 -> 8 | 12 -> 12 |
| Drop seed 2 / top-1 | 12 | 2.167 -> 1.792 | 5 -> 6 | 7 -> 8 | 7 -> 8 | 12 -> 12 |

The new command prints each rule anchor, its nearest organizer second, signed/absolute offsets, the best offset per clip, and the service top-1. Its final JSON includes means, tolerance counts and best-per-clip aggregates per rule. Identical files retain both reference seconds: Х-4/Х-47 has labels 57 and 68. Legacy replays without `ranked_findings` get no top-1 measurement; chronological order is not assumed to be service order.

```bash
export API_KEY=x PYTHONPATH=.
PY=/home/sultanbek/projects/hackathons/dt26-lab/venv/bin/python
$PY scripts/replay_f1.py run --cache-dir /home/sultanbek/projects/hackathons/dt26-lab/perception_cache > /tmp/timecode.jsonl
$PY scripts/replay_f1.py timing /tmp/timecode.jsonl --labels data/prepared/videos.jsonl
```

2. Per caught violation clip: evidence, anchors and results

All times below are seconds from the full-cache replay. Raw finding times remain unchanged; offsets are finding time minus the nearest organizer second. A caught verdict does not establish that the correct violation type was detected.

| Clip | Organizer | Rule anchors and offsets | Cached evidence / action / result |
| --- | --- | --- | --- |
| Х-4 / Х-47 | 57, 68 | `C-ID-BEFORE-CASH@66.0`, -2.0 from 68, +9.0 from 57 | Cash in 20/145 observations; first qualifying handover at 66.0. Sheet describes uncleared/mixed cash. Different mechanism; no retiming. |
| Х-15 | 15 | `L-NO-CASH-ON-LEAVE@10.5` (-4.5), `@15.0` (0.0) | Bag in 35/42 observations. Absences 10.5-14.0 and 15.0-17.0; only the latter contains the same cashier's confirmed EXIT at 17.0. Both confidence scores are 0.2744486034. Added exit corroboration as the last ranking tie-break. UI first anchor 10.5 -> 15.0. |
| Х-18 | 20 | `A-SECOND-PERSON@19.5` (-0.5) | Sustained second-client event spans 19.5-20.5. Already relevant; unchanged. |
| Х-20 | 5 | `L-NO-DOCS-ON-LEAVE@1.0` (-4.0) | Document in 8/23 observations; safe classified closed in 23/23. Sheet describes an open safe. This is a different-rule catch, not an anchor lag; unchanged. |
| Х-24 | 8 | `L-NO-DOCS-ON-LEAVE@8.0` (0.0) | Tablet track survives the absence starting at 8.0; confirmed EXIT at 10.5. Already matches departure onset; unchanged. |
| Х-26 | 9 | `L-NO-CASH-ON-LEAVE@12.5` (+3.5) | Cash in 23/40 observations. Away 11.0-12.0 is too short; qualifying absence 12.5-15.0, EXIT 15.0. No supported desk departure at 9.0 in the event log; unchanged. |
| Х-28 | 7 | `L-PC-LOCKED@8.0` (+1.0) | Working screen at the away onset 8.0. No principled reason to subtract a second; unchanged. |
| Х-30 | 13 | `A-OUTSIDER-ZONE@13.0` (0.0) | Outsider condition 13.0-19.0. Already relevant; unchanged. |
| Х-34 | 13 | `C-COUNT-BEFORE-EXIT@15.0` (+2.0) | COUNT_START 13.0, observed client EXIT / SESSION_END 15.0. The rule anchors client exit, not count start; unchanged. |
| Х-38 | 33 | `S-CLEAN-DESK-HANDOVER@32.0` (-1.0) | Prior client EXIT 27.5, next session 32.0, earlier cash still on desk. Already relevant; unchanged. |
| Х-40 | 17 | `W-NO-PERSONAL-ITEMS@19.5` (+2.5) | Earlier handbag interval 16.0-17.5 and coat interval 16.5-18.5 fail the >3 s duration. Qualifying coat track is 19.5-24.0. Joining different tracks only to recover the label would need new evidence; unchanged. |
| Х-46 | 11 | `W-NO-FOOD@12.0` (+1.0), `@15.5` (+4.5) | Cup in 10/38 observations, first at 12.0; food in 0/38. Both head-contact intervals last 1 s. Earliest supported sip is already first; unchanged. |

The nine missed unique clips remain missed. There is no existing finding to move:

| Clip | Organizer | Cached limitation / result |
| --- | ---: | --- |
| X-1 | 22 | Cash in 0/52 observations; counter coverage false. No cash handover anchor. |
| X-2 | 10 | Cash and ID-card labels each in 0/34 observations; no cash handover. |
| Х-11 | 18 | Laptop classified closed in 51/51 observations, including departures. No working-screen finding. |
| Х-13 | 47 | Bundles in 0/131 observations; 0 cash-to-safe state events, despite cash in 22 observations. |
| Х-17 | 7 | Bag in 7/29 observations, but 0 bag handovers among 7 HANDOVER events. No `K-SEAL-CHECK` finding before or after. |
| Х-22 | 14 | F1 has no `L-SAFE-LOCKED-ON-LEAVE` implementation. Cashier EXITs at 17.5 and 19.5 do not establish a key left in a lock. |
| Х-32 | 5 | ENTER at 2.0; DOOR_CLOSED at 0.0 and repeated HAND_ON_DOOR events. No qualifying open-door finding. |
| Х-33 | 6 | ENTER at 6.0 is not marked observed; DOOR_CLOSED at 7.0. No qualifying entry/open-door finding. |
| Х-44 | 16 | `C-DETECTOR-CHECK` is disabled in the Knowledge Pack and absent from F1's implemented rules. No enabled finding. |

`K-SEAL-CHECK` now anchors collector EXIT instead of bag HANDOVER. Its configured anchor says "Collector exit", and inspection can still occur between handover and exit. The original handover time is retained as `handover_sec`; the bag box is refreshed from the exit observation, or omitted when unavailable, instead of drawing handover geometry at another time. This changes a supported semantic error, not any of the 40 clips' labels.

3. Other changed clips

None. No verdict regressions, no changed raw finding lists, and no other ranked list changes in full or dropped runs. Clean false alarms Х-14 and Х-35 remain unchanged. Х-14 retains docs before cash at 62.5 s because their scores differ; the new tie-break does not override scores or rule order.

4. Rule-hit timing

The caught-clip table above lists every enabled-rule hit on full-cache violation clips. Best-per-clip mean absolute offsets per rule are unchanged: `A-OUTSIDER-ZONE` 0.0; `A-SECOND-PERSON` 0.5; `C-COUNT-BEFORE-EXIT` 2.0; `C-ID-BEFORE-CASH` 2.0; `L-NO-CASH-ON-LEAVE` 1.75; `L-NO-DOCS-ON-LEAVE` 2.0; `L-PC-LOCKED` 1.0; `S-CLEAN-DESK-HANDOVER` 1.0; `W-NO-FOOD` 1.0; `W-NO-PERSONAL-ITEMS` 2.5 s. For cash-left findings specifically, top-1 mean absolute offset improves 4.0 -> 1.75 s across its two caught clips. There are zero `K-SEAL-CHECK` hits across all four runs.

5. Files, tests and rejected approaches

- `scripts/replay_f1.py`: added `timing` and service `ranked_findings`; preserved raw findings for verdict comparison. No dependency added.
- `backend/f1/rules.py`, shared helper `left_with`: only adds `confirmed_exit` metadata, requiring the same actor's EXIT within that particular absence. Existing predicates, confidence and timestamps are untouched. The separate `k_seal_check` function changes its anchor and refreshes evidence geometry.
- `backend/rules/ranking.py`, shared ranking: only breaks ties after equal score and equal known rule position, preferring a confirmed exit. No rule weights, thresholds, caps or score semantics changed. F1 still supplies confidence as its rank score; this audit did not redefine that contract.
- `tests/test_replay_f1.py`, `tests/test_f1_timing.py`, `tests/test_rules_ranking.py`: 19 new parameterized test cases covering scoring, duplicate labels, exact tolerances, legacy results, service ordering, seal anchors/boxes, actor/absence boundaries and ranking precedence. The seal/confirmation tests were observed failing before implementation.
- `REPORT-ORCH.md`, `attempts/A21-timecode-anchors/README.md`, `attempts/README.md`: report and experiment record. No events, calibration, configuration, generated files or CHANGELOG edits.

Validation command:

```bash
$PY -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py tests/test_replay_f1.py tests/test_f1_timing.py tests/test_rules_ranking.py --deselect tests/test_f1_detector.py::test_extract_frames_produces_one_jpeg_per_step
```

Result: **157 passed, 1 skipped, 1 deselected**. The existing GPU end-to-end test is skipped; the synthetic video-extraction test was explicitly deselected to respect the no-frame-extraction restriction. Ruff check and format pass on all six changed Python files. Repository-wide Ruff reports 480 existing errors, all in unchanged files: 66 under `attempts/`, 414 under `validation/`. `git diff --check` passes. Both `timing` CLI dispatch and all four replay/score variants ran successfully.

Investigated but not implemented: a constant leave offset (cash-left errors have opposite signs), moving the count-before-exit anchor to count start, joining personal-item track fragments just to recover an earlier time, and moving a different-rule catch toward an open-safe label. No such experimental offset was committed or claimed as an improvement.

No image-level evidence review, GPU inference or new-camera evaluation was performed. Evidence relevance is supported by cached events and refreshed geometry, not visual inspection; the missing and different-rule catches remain limitations.
