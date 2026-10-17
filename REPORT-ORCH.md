Branch: `orch/leave`, baseline `ac6fe47` from `night`. Offline replay only, using cached numbers and the supplied workbook. No dataset frames, VM, network, new models, or per-clip rule exceptions.

1. Scores before and after

Before, freshly rerun with `scripts/replay_f1.py score`:

```text
full   {"videos": 40, "correct": 26, "clean_false_alarm": 4, "missed": 10, "outsider_on_clean": 0}
drop0  {"videos": 40, "correct": 24, "clean_false_alarm": 2, "missed": 14, "outsider_on_clean": 0}
drop1  {"videos": 40, "correct": 27, "clean_false_alarm": 2, "missed": 11, "outsider_on_clean": 0}
drop2  {"videos": 40, "correct": 25, "clean_false_alarm": 3, "missed": 12, "outsider_on_clean": 0}
```

After, using the production implementation:

```text
full   {"videos": 40, "correct": 27, "clean_false_alarm": 3, "missed": 10, "outsider_on_clean": 0}
drop0  {"videos": 40, "correct": 26, "clean_false_alarm": 1, "missed": 13, "outsider_on_clean": 0}
drop1  {"videos": 40, "correct": 27, "clean_false_alarm": 2, "missed": 11, "outsider_on_clean": 0}
drop2  {"videos": 40, "correct": 26, "clean_false_alarm": 2, "missed": 12, "outsider_on_clean": 0}
```

`dropN` means `--drop 0.2 --seed N`.

| Mean | Correct /40 before -> after | Clean false alarms before -> after | Missed before -> after |
|---|---|---|---|
| Three loss seeds | 25.33 -> 26.33 | 2.33 -> 1.67 | 12.33 -> 12.00 |
| All four runs | 25.50 -> 26.50 | 2.75 -> 2.00 | 11.75 -> 11.50 |

The full-data goal is met, and mean accuracy under loss improves by one video. No video verdict changes for the worse in any run.

2. Target evidence, mechanism and result

The item rules now require an away interval lasting at least the existing two-second confirmation delay. This filtering happens before departure deduplication, so a short reach-boundary excursion cannot hide the next sustained departure. Confirmed EXIT events remain departure candidates. Other leave callers retain their existing 0.6-second minimum.

For an item to count, the same track must occur in at least two distinct observations in each of `[t-1, t+1]` and `[t+2, t+4]`. Each window normally contains five observations at the cache's 2 fps. The window lengths reuse `LEFT_BEHIND_SEC = 2`, with no clip-specific tuning. Every observation uses the existing desk, fixture and hand filters. Missing or repeated timestamps cannot be replaced by copies of a nearest frame, and a recording ending too early provides no later evidence.

- Х-8: `document:1` has 59 detections from 0.0 to 29.0 s, no hand contacts, and centre ranges of only 0.001 horizontally and 0.002 vertically. Presence from frame zero alone does not establish that it is a fixture. The actual bug is the departure: the hips briefly cross the existing 0.25 laptop-reach boundary at 9.5 s (distance 0.260), then return inside at 10.5 s (0.236). The old rule checks the document at 11.5 s, after the cashier has returned. The one-second absence now fails confirmation. The later 28.0 s away interval has no document evidence in its 30.0-32.0 s confirmation window. Result: clean on full data and all three seeds.
- Х-20: `document:2` is observed at 0, 1, 1.5, 2, 3, 3.5, 4.5 and 5 s. The 1.0-4.0 s away interval lasts three seconds. Full-data support is 4 observations in each window, 0-2 and 3-5 s. Seed 0 loses the exact 3.0 s detection that previously removed the finding, but retains 3.5, 4.5 and 5.0 s. Window support before/after the delay is 3/3, 4/4 and 3/4 for seeds 0/1/2. Result: `L-NO-DOCS-ON-LEAVE@1.0` in all four runs. Limitation: the workbook describes an open safe at 5 s while the cashier sits down. This is an incidental video-level match, not a correct explanation of the organizer's violation.
- Х-26: `cash:4` has 23 detections from 8.5 to 19.5 s and remains on the desk from 10.5 s. The 11.0-12.0 s away interval is too short; the next eligible interval is 12.5-15.0 s. Support in 11.5-13.5 and 14.5-16.5 s is 5/5 on full data, and 5/4, 5/5, 2/4 for the three seeds. Seed 2 even loses the detection at the new 12.5 s finding anchor. Result: `L-NO-CASH-ON-LEAVE@12.5` in all four runs. On the freshly rerun baseline, seeds 0 and 2 lose the 11.0 s finding but retain a second finding at 16.0 s, so their whole-video verdicts were already correct.

3. Other changed clips and regressions

- Full data: the only verdict change is Х-8, violation -> clean.
- Seed 0: Х-8 becomes clean and Х-20 changes from missed to caught.
- Seed 1: no verdict changes.
- Seed 2: only Х-8's verdict changes, to clean.
- Х-14 remains a false alarm in every run, including from unchanged personal-item rules. On full data and seed 0, the documents finding at 74.5 s disappears because only one post-delay observation survives the desk/hand filters. Seed 1's documents finding moves from 74.5 to 62.5 s. Seed 2 restores cash and documents findings at 62.5 s through corroboration; both findings already exist on full baseline data. These false leave findings remain a limitation, although no new clean-video verdict is introduced.
- Х-15's disabled bag rule keeps its 10.5 and 15.0 s findings. The old 19.5 s finding disappears: its required later window begins at 21.5 s, beyond the 21.0 s recording. Previously nearest-frame reuse invented continued presence. The scored verdict is unchanged because `L-NO-BAG-ON-LEAVE` is absent from the enabled knowledge rules.

There are no other changed scored findings beyond Х-8, Х-14, Х-20 and Х-26 across the four runs. Х-24's documents finding and Х-28's PC finding survive unchanged in every run.

4. Finding times versus organizer timestamps

All current leave findings on violation clips are listed below. Offset is finding minus organizer second. Their new times are identical across the full run and all three seeds.

| Clip / rule | Organizer | Full-data baseline findings | Current findings | Current offsets |
|---|---|---|---|---|
| Х-15 / L-NO-BAG-ON-LEAVE, disabled | 15 | 10.5, 15.0, 19.5 | 10.5, 15.0 | -4.5, 0.0 |
| Х-20 / L-NO-DOCS-ON-LEAVE | 5 | 1.0 | 1.0 | -4.0 |
| Х-24 / L-NO-DOCS-ON-LEAVE | 8 | 8.0 | 8.0 | 0.0 |
| Х-26 / L-NO-CASH-ON-LEAVE | 9 | 11.0, 16.0 | 12.5 | +3.5 |
| Х-28 / L-PC-LOCKED | 7 | 8.0 | 8.0 | +1.0 |

The offsets have different causes, so no global clock correction is justified. Х-26's first hit is now 1.5 s later than baseline because the earlier one-second interval cannot confirm an item left behind. Its remaining delay reflects the cached reach-boundary crossings, not a constant clock error. Х-20's annotation describes a different rule. Х-15 has an early workstation-away event and a second event matching the annotation. Х-28's away event follows a person-track gap; its PC logic is unchanged. Clean clips Х-8 and Х-14 have no organizer violation timestamps.

5. Files, shared code, verification and negative results

- `backend/f1/rules.py`: only production code changed. `Context.leaves` gains a minimum-away argument, `items_on_desk` factors out the existing spatial filter, `persistent_on_desk` counts distinct observed timestamps, and `left_with` uses repeated track evidence. `on_desk` keeps its previous single-frame behavior for other rules. The A18 desk-object path retains its existing object-presence checks, with the same new departure-duration filter. No changes to `events.py`, `calibration.py`, configuration, generated files, or other rule implementations.
- `tests/test_f1_rules.py`: 16 new regression cases cover lost detections at either exact check time for cash, documents and bags; one-off, stale and duplicated evidence; nearby-frame reuse; short absences; filtering before deduplication; and recordings ending too early. Existing positive and fixture tests now supply actual repeated observations instead of relying on nearest-frame extrapolation.
- `REPORT-ORCH.md`, `attempts/ORCH-leave-persistence/README.md`, and one row in `attempts/README.md`: requested report, reproduction instructions and attempt history.

Required suites: `94 passed, 1 skipped`. The skip is the existing model-weight end-to-end test. Running the 16 new cases with baseline `left_with` and `leaves` restored in memory gives `16 failed`; no repository rollback was needed. Ruff check and format pass for both changed Python files, and `git diff --check` passes. Whole-repository Ruff has 480 pre-existing errors, all outside changed code: 66 under `attempts/` and 414 under `validation/`.

An isolated numeric prototype produced the same four scores as the implementation; no threshold sweep or other implementation variant was needed. Rejected by inspection, not benchmarked: dropping all objects present in the first frame would remove Х-20's `document:2` as well. A18 image/background extraction was not rerun. For Х-22, the cache contains 42 observations, zero key detections and no key/lock state family. `L-SAFE-LOCKED-ON-LEAVE` has no F1 implementation today; safe open/closed classification and hand proximity cannot establish whether a key remains in the lock. That missing signal remains unresolved.

Local evidence logs are `/tmp/leave-before-{full,drop0,drop1,drop2}.{jsonl,txt}`, `/tmp/leave-after-{full,drop0,drop1,drop2}.{jsonl,txt}`, `/tmp/leave-evidence.txt`, `/tmp/leave-red-baseline.txt` and `/tmp/leave-existing-ruff.json`. Reproduction commands are in the attempt README. Nothing was pushed.
