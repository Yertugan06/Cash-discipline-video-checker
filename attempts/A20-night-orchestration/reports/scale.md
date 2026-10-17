Committed locally as `a5dcdd5` on `orch/scale`. Worktree is clean. The full report is saved and committed in [REPORT-ORCH.md](/home/sultanbek/projects/hackathons/dt26-wt/scale/REPORT-ORCH.md).

1. Scores before and after

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

Full-data findings are unchanged. Every requested zoom and mirror now matches their rule IDs and timestamps exactly.

2. Target clips and mechanisms

Physical distances now use `old_distance × desk_long_side / 0.70`. The measured original desk-span median was 0.7072; the reference was selected before testing the fix.

| Clip | Cached evidence and change | Final result |
|---|---|---|
| Х-20 | Hip-to-laptop distance at 1 s changes from 0.3039 to 0.2431 under zoom 0.8, crossing the fixed 0.25 reach. Scaling calibration and away detection together preserves the anchor. | Original docs-left finding at 1 s survives every zoom. Its mismatch with the labeled open-safe action remains. |
| Х-38 | At 31.5 s, cash-to-hand gap shrinks from 0.0703 to 0.0562, falsely becoming “held” under the old 0.07 threshold. Corrected zoom-0.8 threshold is about 0.0533. | Desk-handover finding restored at 32 s. |
| Х-5 / Х-48, clean | At 35/35.5/36 s, apparent client feet are 0.0245/0.0305/0.0367 above the desk. Zoom 0.8 puts all three inside the fixed glass margin. | Scaled glass/service margins remove the false second-person finding. |
| Х-34 | Zoom-1.2 laptop hand margins needed are 0.0843/0.0832/0.0818/0.0753. Only one fits the old 0.08 threshold. | Scaled margin 0.0865 supplies four calibration frames; count-before-exit restored at 15 s. |
| Х-10, clean | Zoom 1.1 invents an away interval at 1-4 s and findings at 1 s. | Scaled reach removes the interval and findings. |
| Х-8, clean | Zoom 1.1 creates docs findings at 1.5/10.5/22 s. | Consistent reach and item geometry remove all false findings. |
| Х-15 | Leave time shifts to 17 s at zoom 0.8 and 13.5 s at higher zooms. | Restored to 15 s throughout. |
| Х-18 | Second-person finding shifts to 18 s at zoom 0.8. | Restored to 19.5 s. |
| Х-24 | Docs-left times vary from 6 to 10.5 s. | Restored to only 8 s. |
| Х-26 | Cash-left times vary from 10.5 to 15 s. | Restored to only 12.5 s. |
| Х-46 | Smaller zoom adds food findings at 13/18 s; larger zoom loses 12 s. | Restored to exactly 12/15.5 s. |
| Х-4 / Х-47 | Larger zoom moves the ID-before-cash finding from 66 to 63.5 s. | Scaled ownership restores 66 s. |
| Х-14, intermediate failure | Fixed calibration margin selects a small desk box spanning 0.1914/0.2088 at higher zooms. | Scaling that margin before desk selection removes the trial false alarm at 31 s. |

3. Other verdict changes and border effects

There are no regressions across the nine comparisons.

- Zoom 0.8 recovers Х-20/Х-38 and removes the Х-5/Х-48 false alarm.
- Zoom 1.1 recovers Х-20 and removes false alarms on Х-8/Х-10.
- Zoom 1.2 recovers Х-20/Х-34.
- Full data, zoom 0.9, mirror, and drop verdicts remain unchanged.

The 0.12/0.18 frame-border tests and pose visibility bounds remain image-relative. No entry/exit flags or event times change across the final zoom runs, so no border exception is needed here.

4. Final finding times versus organizer timestamps

| Clip | Rule | Finding s | Organizer s |
|---|---|---:|---:|
| Х-30 | A-OUTSIDER-ZONE | 13 | 13 |
| Х-47 / Х-4 | C-ID-BEFORE-CASH | 66 | 68 / 57 |
| Х-38 | S-CLEAN-DESK-HANDOVER | 32 | 33 |
| Х-46 | W-NO-FOOD | 12, 15.5 | 11 |
| Х-15 | L-NO-CASH-ON-LEAVE | 15 | 15 |
| Х-40 | W-NO-PERSONAL-ITEMS | 19.5 | 17 |
| Х-20 | L-NO-DOCS-ON-LEAVE | 1 | 5 |
| Х-18 | A-SECOND-PERSON | 19.5 | 20 |
| Х-24 | L-NO-DOCS-ON-LEAVE | 8 | 8 |
| Х-28 | L-PC-LOCKED | 8 | 7 |
| Х-26 | L-NO-CASH-ON-LEAVE | 12.5 | 9 |
| Х-34 | C-COUNT-BEFORE-EXIT | 15 | 13 |

Х-20 and Х-4/Х-47 retain baseline rule/action mismatches; preserved verdicts do not establish correct event recognition.

5. Files, tests, and unsuccessful work

Shared code touched: `vision_types.py`, `calibration.py`, `events.py`, and `rules.py`. Changes convert existing physical distances through one scene-scale implementation. **`in_zone` now scales margins internally; callers should pass reference distances once.**

Also changed: a units comment in `config/perception.yaml`, one existing test fixture, new `tests/test_f1_scale.py`, the report, and attempt documentation.

- Tests: **428 passed, 1 existing model-backed test skipped**.
- New coverage: 277 synthetic cases; **95 fail against the original implementation**, spanning all 15 new test functions.
- Changed Python files pass Ruff lint and formatting.
- Repository-wide Ruff retains exactly the same 480 historical findings.
- The rejected intermediate fix scaled downstream geometry alone, causing Х-14 false alarms at higher zooms. Correcting desk selection removed them without changing the reference constant.

GPU inference and deployment were not run. The nine baseline misses remain; robustness still depends on obtaining a reliable desk calibration.