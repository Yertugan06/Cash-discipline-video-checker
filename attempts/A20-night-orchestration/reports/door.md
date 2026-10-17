# A-DOOR-LOCK: reject a first-observation entry claim

Branch: `orch/door`. Baseline commit: `0ab0258e56aeea0714888324a09d5bf00ea9c95e`.
Used only source code, cached numeric observations, organizer labels, and the team's
workbook. No videos, images, VM access, network calls, or new perception were used.

## 1. Score before and after

Before, reproduced on the 40 unique cached videos:

```json
{"videos": 40, "correct": 25, "clean_false_alarm": 5, "missed": 10, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 26, "clean_false_alarm": 4, "missed": 10, "outsider_on_clean": 0}
```

One improved verdict, no regressed verdicts, and unchanged violation recall (11/21).
The two missed door targets remain missed because the cache does not support a
sustained open door after the cashier arrives. This is a limited precision fix.

## 2. Target clips: evidence, change, result

All coordinates below are normalized. Counts are cached observation samples at 2 fps,
not independent classifier decisions; successive half-second samples often repeat
the same CLIP state. Scores and margins are rounded to three decimals.

| Clip | Organizer label/time | Open / closed / unknown samples | Result before -> after |
|---|---|---|---|
| Х-29 | Clean | 22 / 6 / 7 (35 total) | Door finding at 0.0 s -> clean |
| Х-32 | Violation, 5 s | 4 / 24 / 15 (43 total) | Missed -> missed |
| Х-33 | Violation, 6 s | 14 / 4 / 11 (29 total) | Missed -> missed |
| Х-30 | Violation, 13 s | 0 / 34 / 4 (38 total) | Outsider at 13.0 s -> unchanged |
| Х-46 | Violation, 11 s | 20 / 4 / 14 (38 total) | Door + food findings -> food findings retained |

**Х-29.** The calibrated door box is `[0.000, 0.000, 0.354, 0.576]`.
At 0.0 s, `person:1` is already seated near the laptop, with hip position
`[0.403, 0.494]`. The door-zone test allows a 0.05 margin, so this position
counts as on the door even though there was no preceding observation of an entry.
`EventBuilder` consequently emits `ENTER@0.0` with `observed_entry=True`.
The door is classified open throughout 0.0-5.5 s: scores 0.558-0.633,
margins 0.117-0.267. No hand contact occurs in the rule's 0.0-5.0 s window.
The old rule therefore reports the entry timestamp, 0.0 s, after evaluating that
window. The finding is an unsupported entry claim, not proof of an entry at 0.0 s.
The workbook's clean behavior is screen locking at 6 s followed by departure.

The fix requires `ENTER.timestamp_sec` to be strictly later than the first cached
observation. It uses the observation boundary rather than a tuned startup delay
or a confidence cutoff. A person already visible when recording starts cannot
establish an observed crossing. The later `ENTER@13.5` lacks the complete 5 s
follow-up window in this 17.5 s replay, so it produces no finding either.

**Х-32.** The calibrated door box is `[0.000, 0.001, 0.352, 0.554]`.
`person:2` has an observed `ENTER@2.0`, becomes cashier at 4.0 s, and generates
`HAND_ON_DOOR` events at 2.0, 3.5, 5.0, 6.5 s and later. That large door region
also overlaps the cashier's projected workstation position; contact with it is
not reliable proof of closing. Independently of that suppression, the cache
classifies the door closed at the organizer's 5 s mark (score 0.763, margin 0.527).
The only open samples are 7.0, 7.5 s (score 0.562, margin 0.124), and 18.0, 18.5 s
(score 0.585, margin 0.170). Each burst has only 0.5 s between its first and last
sample, below the existing 0.6 s hysteresis; no `DOOR_OPEN` event is emitted.
The stable state at the entry deadline, 7.0 s, is still closed. There is no
5 s open-door observation to recover. No threshold was changed to force a hit.

**Х-33.** The calibrated door box is `[0.000, 0.000, 0.190, 0.545]`.
There are no person detections through 4.5 s. `person:14` first appears at 5.0 s,
but is filtered as glass at 5.0 and 5.5 s. It is retained at 6.0 s, with hip
position `[0.320, 0.364]`, outside the door zone including its 0.05 margin.
Its `ENTER@6.0` therefore has `observed_entry=False`; it becomes cashier at 7.0 s.
The door is open from 0.0 through 5.5 s (scores 0.615-0.740, margins 0.230-0.480),
unknown at 6.0-6.5 s (score 0.531, margin 0.062), and closed at 7.0-7.5 and
9.0-9.5 s (scores 0.562-0.574, margins 0.124-0.147). After cashier arrival,
the only raw open burst is 12.0-12.5 s (score 0.566, margin 0.132), again too
short for hysteresis. Stable events are `OPEN@0`, `CLOSED@7`, `UNKNOWN@11`.
Simply treating the 6 s appearance as a confirmed entry would still encounter
`DOOR_CLOSED@7` inside the follow-up window.

The possible outsider is `person:20`, present at 11.5-14.0 s in six samples.
All six are filtered as glass: box bottoms are about 0.372-0.373, above
`desk.top - glass_margin = 0.427 - 0.030 = 0.397`. Thus the outsider rule has
no retained second-person interval. `person:22` is also filtered in all four of
its samples. These boxes alone cannot establish which side of the glass they
occupy. No shared glass-filter or outsider-rule change was made.

**Х-30.** Door CLIP has no open samples at all; closed scores are 0.562-0.922
with margins 0.124-0.845. `person:23` produces a retained outsider interval
13.0-19.0 s, lasting 6.0 s. `A-OUTSIDER-ZONE@13.0` remains unchanged and matches
the organizer's 13 s mark exactly.

**Х-46.** A seated `person:1` already visible at the first observation creates
the same unsupported `ENTER@0.0`. At the rule deadline the stable door state is
open (`DOOR_OPEN@2.0`), so the old rule reports 0.0 s. The fix removes that
finding. The workbook labels food/drink at 11 s, and `W-NO-FOOD@12.0` and
`W-NO-FOOD@15.5` remain unchanged. The clip stays caught; the nearest retained
finding is 1.0 s after its organizer mark.

## 3. Other clips and all clean door checks

No non-target clip changed verdict or findings. The complete finding diff is:

| Clip | Finding removed | Findings retained | Verdict change |
|---|---|---|---|
| Х-29 | `A-DOOR-LOCK@0.0` | None | Violation -> clean, correct |
| Х-46 | `A-DOOR-LOCK@0.0` | `W-NO-FOOD@12.0`, `W-NO-FOOD@15.5` | None |

All 19 unique clean clips have zero door findings after the change:
Х-3, Х-8, Х-10, Х-12, Х-14, Х-16, Х-19, Х-21, Х-23, Х-25, Х-27, Х-29,
Х-31, Х-35, Х-37, Х-39, Х-43, Х-45, Х-48.
The four remaining clean false alarms are unrelated rules on Х-8, Х-14, Х-35,
and Х-48. No attempt was made to change them.

## 4. Door finding time versus organizer timestamp

There are **no surviving A-DOOR-LOCK findings on violation clips**, so there is
no post-change door timecode match to claim. Х-32 (5 s) and Х-33 (6 s) remain
missed. Before the change, the only door hit on a violation clip was Х-46 at
0.0 s, 11 s before its food/drink label; that unsupported hit is removed.
Х-30 remains caught by the outsider rule at exactly its 13 s label, and Х-46
by food at 12.0 s (+1.0 s) and 15.5 s (+4.5 s).

## 5. Files, tests, rejected directions, and limits

Files touched:

- `backend/f1/rules.py`: only `a_door_lock`, adding the first-observation guard.
  This shared file contains other implementers' rules, but no helper, other rule,
  event contract, calibration, or event-builder code changed.
- `tests/test_f1_rules.py`: four parameterized cases checking startup rejection
  and valid later entries, for recordings starting at both 0 s and 2 s. The
  common fixture now starts at 0 s, before its synthetic entry at 1 s.
- `REPORT-ORCH.md`: this report.

The new regression test was run before the fix: **2 failed, 2 passed**. Both
failures were startup entries; the later-entry controls already passed.
After the fix, the required command passed: **78 passed, 1 skipped**.
The skip is the existing model smoke test at `tests/test_f1_detector.py:159`,
which requires model weights and heavyweight perception dependencies.

Ruff formatting and lint passed for both changed Python files. A read-only
repository-wide check also ran: it reports 480 existing lint issues in 35
unchanged files (66 issues under `attempts`, 414 under `validation`), and
39 unchanged files needing formatting. Neither changed Python file has an
issue. Historical and validation files were left untouched. `git diff --check`
passed.

Rejected directions investigated from the cached numbers:

- Removing hand-contact suppression alone does not fix either missed target:
  Х-32 has no stable open state and Х-33 lacks an observed entry and has a closed
  state inside the follow-up window. A diagnostic counterfactual would also add
  a clean false alarm on Х-12 at 34.5 s: a replacement cashier track is treated
  as an entry while door CLIP is already open. This was not shipped.
- Applying a global open-door/workstation test without observed entry would
  contradict clean Х-43: it has 43/47 open samples (scores 0.566-0.772,
  margins 0.132-0.544), with a cashier in 45/47 samples. Its stable door state
  is open for the entire clip. Startup state alone does not distinguish clean
  and violation clips in this cache. This was not shipped.
- Shortening hysteresis would admit the isolated open bursts in Х-32 and
  Х-33, but would not supply a sustained open door after entry. Discarding the
  closed states or extending open through long unknown spans would invent
  supporting evidence. No hysteresis, score, margin, duration, or geometry
  thresholds were changed.

The rule still depends on an observed entry, cached door classification, and
the pre-existing hand-contact suppression. It cannot verify a physical lock.
Recovering the two target misses requires better door-state/crop evidence and,
for Х-33's outsider, a reliable way to distinguish a person behind the desk
from a glass reflection. This branch deliberately makes no broader recall claim.

Replay artifacts are `/tmp/door-before.jsonl`, `/tmp/door-after.jsonl`, and
`/tmp/door-after-score.txt`. Numeric diagnostics are in `/tmp/door-diagnostics.json`
and `/tmp/door-targets.txt`; `/tmp/door-inspect.py` reproduces those diagnostics.
They are temporary local files, not committed generated artifacts.

Commands used for the final checks:

```bash
export API_KEY=x PYTHONPATH=.
ORCH=/tmp/claude-1000/-home-sultanbek-projects-hackathons-datathon26/63bd15ca-5dd2-4bc8-a818-01aa3c847602/scratchpad/orch
PY=$ORCH/venv/bin/python
$PY scripts/replay_f1.py run --cache-dir "$ORCH/perception_cache" > /tmp/door-after.jsonl
$PY scripts/replay_f1.py score /tmp/door-after.jsonl --labels data/prepared/videos.jsonl
$PY -m pytest -q -rs tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
$PY -m ruff format backend/f1/rules.py tests/test_f1_rules.py
$PY -m ruff check backend/f1/rules.py tests/test_f1_rules.py
```
