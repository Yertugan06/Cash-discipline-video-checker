# Money counter fixture correction - orch/counter

## 1. Scores and retained mechanism

Before, reproduced from `night` at `2c728da`:

```json
{"videos": 40, "correct": 27, "clean_false_alarm": 4, "missed": 9, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 24, "clean_false_alarm": 3, "missed": 13, "outsider_on_clean": 0}
```

This is a correctness correction, not a score improvement. Four violation clips lose
accidental money-counter catches, and one clean clip clears. This follows the assignment's
explicit decision to remove those findings even at a cost to whole-video recall.

`PERSONAL_ON_DESK` now excludes detections matching the footprint of a calibrated laptop
or counter, or a repeated alternative laptop/counter calibration candidate. Alternatives
need at least two same-label candidates agreeing at IoU > 0.6. Per-frame calibration NMS
already removes same-label duplicates above 0.4, so overlapping alternatives normally come
from separate calibration samples. The personal detection must also match at IoU > 0.6.
This uses the same overlap level already used for cash/bundle cross-label duplicate
detections, not camera coordinates or clip-specific sizes. No threshold sweep was used.

Repeated alternative equipment candidates make an overlapping handbag label ambiguous.
They do not establish the device's exact identity. A single unselected candidate, mere
proximity, partial overlap, or static presence alone does not exempt an item. Moving the
same track away from the fixture makes it eligible again. No calibration object, state
crop, role, event schema, rule enablement or other event family changed.

Full-data and `--drop 0.2` measurements, each on all 40 unique cached videos:

| Run | Before: correct / clean FP / missed | After: correct / clean FP / missed |
|---|---|---|
| Full | 27 / 4 / 9 | 24 / 3 / 13 |
| Drop seed 0 | 24 / 4 / 12 | 22 / 3 / 15 |
| Drop seed 1 | 28 / 2 / 10 | 25 / 2 / 13 |
| Drop seed 2 | 25 / 4 / 11 | 25 / 2 / 13 |

`outsider_on_clean` stays 0 in every run. Dropping removes non-person detections; cached
states and calibration candidates remain unchanged. These are detection-loss checks,
not new model runs or proof of accuracy on new cameras.

## 2. Per-target evidence and results

Counts below are actual cached detections, not interpolated frames. Coordinates are
normalized. Candidate IoU ranges compare each personal detection with its best raw
laptop/counter candidate. Х-4 and Х-47 are one cached video, as are Х-5 and Х-48; scoring
displays the last label row, Х-47 or Х-48.

| Clip | Cached fixture evidence | Personal finding before -> after; whole-video result |
|---|---|---|
| X-1 | `handbag:69`: 19 detections, 16.5-25.5 s, first box `(0.073, 0.501, 0.272, 0.578)`. No counter candidate. Three secondary laptop candidates match, IoU 0.938-0.990 across the track. | 20 -> none; becomes missed. Spreadsheet: machine count at 14-19 s, manual recount at 20-22 s, return to client at 22.5-24 s. |
| Х-4 / Х-47 | `handbag:1`: 34 detections, 0-22 s, box `(0.073, 0.500, 0.274, 0.579)`. No counter candidate. Three secondary laptop candidates match, IoU 0.938-1.000. | 0, 8.5, 17.5 -> none; stays caught by `C-ID-BEFORE-CASH@66`. Spreadsheet: previous client's cash left at 57 s, cash from two clients together at 68 s. |
| Х-11 | `handbag:50`: 11 detections, 17.5-24.5 s, box `(0.089, 0.435, 0.270, 0.552)`. Three counter candidates; best-candidate IoU 0.682-0.737. | 20.5 -> none; becomes missed. Real violation: laptop left unlocked, organizer 18 s. |
| Х-13 | `handbag:1`: 128 detections, 0-65 s, box `(0.046, 0.370, 0.247, 0.499)`. Three counter candidates match, IoU 0.907-1.000. | 0 -> none; becomes missed. Real violation: cash from opened collection bag stored without recount/accounting, organizer 47 s. |
| Clean Х-14 | `handbag:1`: 90 detections, 0-45 s, box `(0.095, 0.441, 0.266, 0.525)`. Two counter candidates match, IoU 0.791-1.000. Same fixture returns under another track at 121.5-122.5 s. | 0, 34, 39.5 -> none; remains a false alarm from leave rules at 62.5 and 74.5 s. |
| Х-15 | `handbag:2`: 27 detections, 0-19.5 s, box `(0.047, 0.387, 0.252, 0.498)`. Three counter candidates match, IoU 0.887-1.000. | 7 -> none; becomes missed by enabled rules. Real violation: collection bag left unattended at 15 s. |
| Х-40 | `coat:279`: 9 detections, 19.5-25 s, first box `(0.207, 0.432, 0.457, 0.501)`. Best equipment-candidate IoU is only 0.182-0.215. | 19.5 -> 19.5; real coat catch preserved, duration 4.5 s. |
| Clean Х-48 / Х-5 | `handbag:113`: 7 detections, 28-31 s, box `(0.073, 0.503, 0.274, 0.580)`. Sole counter candidate is elsewhere, score 0.121. Three secondary laptop candidates match the item, IoU 0.919-0.971. | 28 -> none; clean false alarm clears. |

### Х-13: K-RECOUNT-BEFORE-SAFE investigation

The cache supports some actions but not a transfer to the safe:

- Bag: 19 detections. `bag:10` is open at 9 and 9.5 s, score 0.689, margin 0.379;
  closed at 10 s. Later `bag:24` states are all closed. No cash overlaps an observed open
  bag, and all eight `CASH_STATE` events have `bag_open_seen=False`.
- Contents: 23 `cash` detections, zero `bundle` detections. Cash is seen at 23.5-36 s
  and once at 42.5 s. There are zero cash, bundle or bag detections at 44-50 s, including
  the organizer's 47 s and the spreadsheet's storage action at 48 s.
- Safe: 119 closed, 10 unknown, 2 open samples out of 131. The only raw open values are
  at 12 and 12.5 s, too brief for the existing 0.6 s stabilization. No `SAFE_OPEN`,
  `HAND_ON_SAFE`, or cash-at-safe event is produced. At 47 s it is closed, score 0.743,
  margin 0.486; at 48 s it is unknown, score 0.520, margin 0.039.
- Calibration: selected safe box `(0.000, 0.582, 0.203, 0.650)` comes from three
  low-score candidates. A single higher-score alternative, 0.252 at
  `(0.461, 0.297, 0.657, 0.441)`, overlaps projected hands at 44-47.5 s. This is a
  calibration ambiguity, not visible proof of storage. Cached safe states describe the
  selected crop; changing the box cannot regenerate states for the alternative crop.
- Counter: idle in 131/131 samples, scores 0.960-0.995, margins 0.921-0.989. No count
  event. Laptop: closed in 131/131; the cache has no accounting/recording signal.

`K-RECOUNT-BEFORE-SAFE` is unchanged and produces no finding on Х-13 or any clean clip.
It cannot establish the target breach from these observations without inventing the
missing cash-to-safe transition. Bag opening plus an absent completed count is insufficient:
clean Х-14 also has zero `COUNT_END` events, zero bag-origin cash states and zero cash-at-safe
states, despite 14 raw running samples at 63-90.5 s. Those occur in isolated pairs 0.5 s
apart and fail stabilization. No generic bag-plus-idle fallback was implemented.

### Report-only handoff for the other rule owners

- **Х-11, L-PC-LOCKED, organizer 18 s:** leave candidates already survive at 11.5,
  17 and 21.5 s. Laptop is classified closed in all 51 samples, overall scores
  0.715-0.978. At 18 s: closed 0.968, margin 0.948; at 22 s: closed 0.933. Clean
  Х-12 is also closed in all 85 samples. The `closed` prompt includes both a closed lid
  and a dark blank screen. The rule needs reliable working-versus-locked/lid evidence;
  no temporal change to this rule can recover working states that are absent.
- **Х-15, collection bag, organizer 15 s:** `bag:4` has 27 detections at 6.5-20.5 s,
  including all 13 samples at 13-19 s. Its box stays around `(0.263, 0.434, 0.471, 0.486)`.
  It is on the desk at 15 and 17 s, scores 0.287 and 0.305, outside both fixture boxes;
  nearest hand distances are 0.168 and 0.254. Away intervals start at 15 s and 18 s;
  cashier exit is 17 s. The existing `L-NO-BAG-ON-LEAVE` function already produces
  findings at 10.5, **15**, and 19.5 s, but its ID is absent from `knowledge/rules.yaml`.
  Enabled `L-NO-CASH-ON-LEAVE` describes cash bags in its knowledge mechanism but its
  F1 implementation checks only cash/bundle labels. The owner can connect this existing
  bag evidence to an enabled rule; this branch changes neither rule nor enablement.
- **X-1, organizer 22 s:** zero cash/bundle detections throughout, zero counter
  calibration candidates, zero counter states or count events, zero cash handovers.
  Cashier hand points exist in all 11 samples at 14-19 s and all 9 at 20-24 s. They
  provide motion geometry, not banknote identity, manual counting or authenticity checks.
  Catching the stated action needs counter activity followed by tracked cash/manual
  counting and return evidence; these signals are absent.
- **Х-4 / Х-47, organizers 57/68 s:** client exit 53 s; next session starts 55.5 s.
  The sole cash track, `cash:15`, first appears at 57 s, with 20 detections through
  67 s, scores 0.326-0.401. Its first box is `(0.290, 0.522, 0.371, 0.544)`, on the
  desk, but it is assigned to the already-active new `session-3`. There is no detected
  cash before that session to establish previous-client ownership. Client fragmentation
  creates `session-4` at 61 s; the same cash moves desk -> cashier hand at 60.5 s ->
  client hand at 61.5 s -> cashier at 66 s. At 68 s there are zero cash detections,
  and no second cash track is ever detected. The handover rule needs continuity across
  the session boundary and correct ownership; mixed cash requires two distinguishable
  origins. Delaying the session check alone cannot supply these facts. The surviving
  ID finding at 66 s does not prove either described cash violation.

## 3. Every other changed verdict

The full run changes exactly five whole-video verdicts: X-1, Х-11, Х-13 and Х-15 become
missed violations for the spreadsheet reasons listed above; clean Х-48 becomes correct.
Х-4/Х-47 and Х-14 lose only personal findings and retain their other findings. Every
finding of every other enabled rule is identical on all 40 videos.

There are no additional full-data changed clips. Clean Х-35 remains a personal-item
false alarm: `coat:1`, 15 detections at 0-7 s, box `(0.353, 0.501, 0.629, 0.532)`;
maximum equipment-candidate IoU 0.012. It is a separate clothing-fragment problem.

For each drop run, these are all whole-video verdict changes relative to its own baseline:

| Seed | Caught violation -> missed | Clean false alarm -> correct |
|---|---|---|
| 0 | X-1, Х-13, Х-15 | Х-48 |
| 1 | X-1, Х-13, Х-15 | none |
| 2 | X-1, Х-13 | Х-14, Х-48 |

Х-11 already has no personal catch in all three dropped baselines; Х-15 is already missed
in seed 2. Х-14 clears in seed 2 because its unrelated leave-rule findings were already
absent in that baseline. No non-personal-rule finding changes in any drop run.

## 4. Finding time versus organizer time

After correction the only violation video hit by W-NO-PERSONAL-ITEMS is Х-40:

| Run | Finding | Organizer | Signed offset | Duration |
|---|---:|---:|---:|---:|
| Full | 19.5 | 17 | +2.5 s | 4.5 s |
| Drop seed 0 | 19.5 | 17 | +2.5 s | 4.5 s |
| Drop seed 1 | 19.5 | 17 | +2.5 s | 4.0 s |
| Drop seed 2 | 20.5 | 17 | +3.5 s | 3.5 s |

The finding and duration are preserved from each corresponding baseline. There are no
K-RECOUNT-BEFORE-SAFE hits to compare. Removed personal findings and their times are in
the per-target table; they never established those clips' described violations.

## 5. Files, validation, rejected approaches and reproduction

Files touched:

- `backend/f1/events.py`: the sole shared runtime file. Adds a fixture-footprint list
  in `EventBuilder.__init__` and a match exclusion in the personal-item branch of `push`.
  Existing gap bridging and removal handling are unchanged. No shared interfaces change.
- `tests/test_f1_rules.py`: four new test functions, 15 parameterized cases.
- `REPORT-ORCH.md`, `attempts/README.md`, `attempts/ORCH-counter-fixtures/README.md`:
  report and attempt history.

Tests cover calibrated laptop/counter aliases; repeated alternative equipment candidates
without a selected counter in original, mirrored and scaled views; real coats/handbags
with only one candidate, partial overlap or non-equipment candidates; and a real item
moving away from the fixture under the same track ID. Against the original runtime,
9 new cases failed and 6 guard cases passed. With the fix all 15 pass. Existing tests
still cover initial personal items, worn/carried items and detection-gap duration.

Required validation: **101 passed, 1 skipped** across `test_f1_rules.py`,
`test_f1_detector.py`, and `test_desk_objects.py`. The skipped full-model test requires
downloaded weights. Ruff check, Ruff format, format check, and `git diff --check` pass.

A selected-counter-only exclusion was rejected during the numeric audit: X-1 and
Х-4/Х-47 have no counter candidates, and Х-48's counter box is elsewhere. Alternative
laptop candidates provide the missing equipment interpretation without relabeling
anything as a calibrated counter. No blanket static-item/first-frame exemption or
broader worn-coat suppression was added; the earlier personal-agent report showed that
the latter also suppresses Х-40. The Х-13 investigation above is the negative result
for the recount rule. No per-clip exception, prompt change, model run, network/VM access
or dataset image/video/frame access was used.

Risk: a real personal item geometrically indistinguishable from a repeated equipment
candidate can be suppressed. Better visual disambiguation needs new perception evidence.
The correction intentionally exposes four missing real-rule catches; it must not be
presented as a whole-video score improvement.

Reproduction from this worktree:

```bash
export API_KEY=x PYTHONPATH=.
S=/tmp/claude-1000/-home-sultanbek-projects-hackathons-datathon26/63bd15ca-5dd2-4bc8-a818-01aa3c847602/scratchpad/orch
PY=$S/venv/bin/python
$PY scripts/replay_f1.py run --cache-dir "$S/perception_cache" > /tmp/counter-after.jsonl
$PY scripts/replay_f1.py score /tmp/counter-after.jsonl --labels data/prepared/videos.jsonl
for seed in 0 1 2; do
  $PY scripts/replay_f1.py run --cache-dir "$S/perception_cache" --drop 0.2 --seed "$seed" > "/tmp/counter-after-drop$seed.jsonl"
  $PY scripts/replay_f1.py score "/tmp/counter-after-drop$seed.jsonl" --labels data/prepared/videos.jsonl
done
$PY -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
$PY -m ruff check backend/f1/events.py tests/test_f1_rules.py
$PY -m ruff format --check backend/f1/events.py tests/test_f1_rules.py
```

Local audit artifacts: `/tmp/counter_audit.py`, `/tmp/counter-audit-before.json`,
`/tmp/counter-audit-summary.txt`, `/tmp/counter-red-tests.txt`,
`/tmp/counter-{before,after}{,-drop0,-drop1,-drop2}.jsonl` and matching `-score.txt` files.
These generated numeric artifacts are not committed.
