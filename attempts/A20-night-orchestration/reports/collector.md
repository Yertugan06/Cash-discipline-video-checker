K-SEAL-CHECK: infer a short bag-delivery visit when the handover is occluded

Branch: `orch/collector`, based on `night` (`8c7406b`). All investigation used local code, cached numbers and the workbook. No dataset videos or frames were inspected; no VM or network access was used.

1. Scores before and after

Actual `scripts/replay_f1.py score` JSON for all 40 cached videos:

Before:

```json
{"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 32, "clean_false_alarm": 0, "missed": 8, "outsider_on_clean": 0}
```

Every requested probe was replayed before and after. Probe baselines used the original `K-SEAL-CHECK` implementation loaded from `HEAD`, without editing the worktree. Other rule implementations are unchanged. Entries below are correct / clean false alarms / missed, on 40 videos.

| Probe | Before | After | K-SEAL-CHECK on Х-17 |
|---|---|---|---|
| Full cache | 31 / 0 / 9 | 32 / 0 / 8 | 9.5 s |
| `--drop 0.2 --seed 0` | 30 / 0 / 10 | 31 / 0 / 9 | 9.5 s |
| `--drop 0.2 --seed 1` | 31 / 0 / 9 | 32 / 0 / 8 | 11.5 s |
| `--drop 0.2 --seed 2` | 31 / 0 / 9 | 32 / 0 / 8 | 9.5 s |
| `--zoom 0.8` | 31 / 0 / 9 | 32 / 0 / 8 | 9.5 s |
| `--zoom 1.2` | 31 / 0 / 9 | 32 / 0 / 8 | 9.5 s |
| `--mirror` | 31 / 0 / 9 | 32 / 0 / 8 | 9.5 s |

Replay outputs are `/tmp/collector-{before,after}-{full,drop0,drop1,drop2,zoom08,zoom12,mirror}.jsonl`; the comparison is `/tmp/collector-probe-summary.json`. These temporary outputs are not committed.

2. Target clips, cached evidence and mechanism

Х-17, violation, organizer 7 s:

- 29 observations at 0.5 s intervals, from 0 to 14 s. The cashier is `person:1`; the visitor is `person:11` throughout all 16 visitor observations, from 4 to 11.5 s. `ENTER` at 4 s has `observed_entry=True`; the confirmed `EXIT` is at 12 s. Both entry and exit call this visitor a `client`, not a `collector`. There are zero bag handover events.
- The only bag track, `bag:16`, is detected in 7/29 observations: 9.5, 11.5, 12, 12.5, 13, 13.5 and 14 s. Scores range from 0.3364 to 0.3931. Its first box is approximately `[0.2671, 0.4422, 0.4499, 0.5091]`, on the desk and outside the calibrated counter/laptop. Five observations confirm it remains at that location after the visitor exits.
- The visitor's hands approach that eventual bag location at 7, 7.5, 8 and 8.5 s. Minimum hand distances, divided by the scene's desk scale, are approximately 0.105, 0.090, 0.092 and 0.084. They increase to 0.140 at 9 s and 0.200 at 9.5 s. The existing carrying reach is 0.12 in these reference units. These are reaches toward the eventual bag area, not observed bag handovers.
- F1 emits `BAG_INSPECTED` at 9.5 s. This event means cashier hand contact, not a visible seal check. It begins after the visitor's last reach toward the bag area at 8.5 s, so it cannot establish inspection during that interaction. The new inference checks inspection only through the observed interaction, rather than accepting later cashier contact as joint inspection.
- Person CLIP states call this visitor seated in 10/16 observations, unknown in two and standing in four. Posture is therefore unsuitable as a decisive signal here and is not used.
- Result: previously missed; now exactly one `K-SEAL-CHECK` finding at 9.5 s, with evidence from that observation and a support window ending at the actual 12 s exit. No handover timestamp is invented.

Х-16, clean twin:

- 45 observations, from 0 to 22 s. Visitor `person:12` enters at 4 s with an observed entry and remains in all 37 subsequent visitor observations through 22 s. There is no visitor exit or lost track. CLIP calls the visitor seated in all 37 observations.
- Bag detections occur in 11/45 observations. Track `bag:12`: 11.5, 12, 12.5, 13 and 13.5 s. Track `bag:17`: 17, 17.5, 18.5, 19, 20.5 and 21.5 s. An inspection-contact event occurs at 17 s. There are zero bag handover events and no collector role here either.
- Result: remains clean on full data and every requested probe. A visitor who stays cannot satisfy the required confirmed exit. The rule does not infer missing documents from absent ID detections.

The inference requires an observed visit beginning after recording starts, a newly appearing desk bag outside workstation fixtures, repeated visitor reaches toward its eventual location, a confirmed visitor exit within the existing 5 s codex limit of its appearance, and the same bag remaining in at least two distinct observations during the existing 2 s confirmation window after exit. Earlier detections under the same track or an overlapping bag track reject pre-existing bags. Observed handovers retain their existing path and exit anchor and are deduplicated against inferred deliveries.

No threshold was fitted to these clips. The implementation reuses the existing codex duration, desk-scaled carrying reach, fixture margin, spatial overlap convention and leave-confirmation window. Synthetic tests cover zoom, mirroring and transposing the camera geometry. The inference is specific to the seal rule and does not relabel visitors or create document violations.

3. Every other changed verdict

None. In every before/after pair, Х-17 is the only clip with any changed finding, not merely the only changed verdict. All 19 clean clips remain clean.

Relative to the full cache, drop seed 0 loses Х-46's existing `W-NO-FOOD` findings. The same loss occurs on the original baseline; this branch does not cause it. All other probe verdicts match their respective full-cache verdicts, apart from the new Х-17 catch.

The only cache clips containing any `bag` detections are Х-17, Х-16, Х-15, Х-14 and Х-13, with 7, 11, 35, 20 and 19 detections respectively. No additional seal finding is introduced on the latter three.

4. Finding time against organizer timestamp

`K-SEAL-CHECK` hits only Х-17 among the violation clips:

- Full cache, zooms, mirror and drop seeds 0/2: 9.5 s versus organizer 7 s, offset +2.5 s.
- Drop seed 1: 11.5 s versus 7 s, offset +4.5 s. The first 9.5 s bag detection was dropped; five detections remain.
- The recorded room exit remains 12 s in every case. The adapter's `window_end` preserves that exit time in the rendered finding, while the evidence anchor uses a bag actually detected at that instant.

An exact 7 s bag-based anchor is unsupported: the first bag detection is at 9.5 s. Backdating to the earlier hand reaches would imply a bag observation the cache does not contain. The 9.5 s anchor is within 3 s of the organizer timestamp; the seed-1 anchor is within 5 s.

5. Files, shared code, tests and rejected approaches

Files touched:

- `backend/f1/rules.py`: add `seal_check_deliveries`, called only by `k_seal_check`; add the inference facts and evidence window. This is the only shared production file touched. `collector_transfers`, `Context`, other rules, event building, role/session contracts and calibration are unchanged.
- `tests/test_f1_rules.py`: 26 new parameterized cases for inferred delivery, camera transformations, required entry/exit/reach/retention evidence, pre-existing/reidentified bags, duplicate boxes in one frame, a bag initially outside the desk, inspection before withdrawal, a longer stay, equipment labels and deduplication.
- `tests/test_f1_timing.py`: one new adapter test for the visible bag anchor, actual exit, support timestamps and evidence box.
- `REPORT-ORCH.md`: this report. No generated files, rule thresholds, CHANGELOG or main project documentation were edited.

Validation actually run:

- Requested three-file pytest command: **177 passed, 1 skipped**.
- Expanded run adding `tests/test_f1_timing.py` and `tests/test_f1_scale.py`: **464 passed, 1 skipped**.
- `tests/test_no_label_access.py` and `tests/test_replay_f1.py`: **11 passed**.
- The existing skipped test requires downloaded perception model weights. No GPU/model end-to-end run was attempted.
- The original seal implementation was substituted in an isolated Python process: all 14 selected new positive/timing cases failed as expected. The worktree was not changed for this check.
- Venv Ruff check, format and format check on the three changed Python files; `git diff --check`.
- Full replay, the six requested perturbation replays, and the timing scorer.

Rejected or insufficient approaches: a mandatory collector role or bag handover still misses Х-17 because neither exists in its cache; trusting `BAG_INSPECTED` alone also misses it because that signal is cashier contact after withdrawal. Posture cannot reliably distinguish standing from sitting in these numbers. An exact organizer-time anchor would require unsupported backdating.

The remaining limitation is perception and attribution: this is a corroborated visit-pattern proxy, not direct recognition of a seal or proof of a handover. It deliberately abstains without a confirmed visitor exit, repeated reach evidence or a retained bag, and relies on the existing person/object tracks. New-camera model performance and the physical seal itself were not checked.
