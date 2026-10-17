Personal items, branch `orch/personal`, 2026-10-18.

**1. Score and retained change**

Before:

```json
{"videos": 40, "correct": 25, "clean_false_alarm": 5, "missed": 10, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 26, "clean_false_alarm": 5, "missed": 9, "outsider_on_clean": 0}
```

Retained one mechanism fix: a brief missed detection does not prove that a personal item
was removed from the desk. `PERSONAL_ON_DESK` now bridges missing observations of the same
track within the existing `exit_gap_sec: 1.2` window. A visible carried/off-desk item ends
the interval. Expiration, confirmed removal and end of video all end at the last positive
sample's end, so trailing uncertainty cannot manufacture a duration over 3 s. Different
track IDs are not joined. No thresholds, prompts, models or rule enablement changed.

**2. Target clips: cached evidence and result**

Coordinates below are normalized `(x1, y1, x2, y2)`. Counts are observed detections, not
interpolated frames. The cache has 40 unique videos. Х-4 and Х-47 share one video; Х-5 and
Х-48 share another. The scorer displays the last label row, Х-47 or Х-48, respectively.

| Clip | Cached evidence | Result after change |
|---|---|---|
| Clean Х-14 | `handbag:1`, 90 detections from 0-45 s, scores 0.232-0.474. First box `(0.095, 0.441, 0.266, 0.525)` matches the calibrated counter: finding-box IoU 0.958-0.984. All 90 centers lie in the counter box. The same fixture reappears as `handbag:352` at 121.5-122.5 s for only 3 samples. | Personal findings `0, 19, 34, 39.5` become `0, 34, 39.5` s because the first two intervals merge. Still a false alarm. Other leave-rule findings at 62.5 and 74.5 s also remain. |
| Clean Х-35 | `coat:1`, 15 detections at 0-7 s, scores 0.219-0.311, first box `(0.353, 0.501, 0.629, 0.532)`: a narrow strip, 0.276 by 0.031. About 84.5-86.8% of its area overlaps `person:1`, but it occupies only about 16-19% of the person's box. The existing worn-coat test requires more than 35%, so it accepts this fragment as a desk item. Larger overlapping coats are already rejected as worn. | Finding remains at 0 s, duration 7.5 s. The numbers suggest a clothing/edge fragment but do not identify the object conclusively. A broader body-overlap filter also rejects the actual desk coat in Х-40; not retained. |
| Clean Х-48 / Х-5 | `handbag:113`, 7 detections at 28-31 s, scores 0.214-0.318, box `(0.073, 0.503, 0.274, 0.580)`. A matching box is present as `handbag:1` at 0 and 0.5 s. No placement is established. The sole counter calibration candidate is elsewhere, `(0.087, 0.230, 0.155, 0.245)`, score 0.121. | Finding remains at 28 s, duration 3.5 s. Cached geometry cannot confidently distinguish a fixture/work tool from a personal bag here. First-frame presence alone cannot exempt an item from a rule about keeping belongings. |
| Х-40 | 51 sampled frames contain 21 coat and 9 handbag detections. At placement: `handbag:96` at 16, 17 and 18 s, with the 18 s detection classified as carried; `coat:236` at 16.5, 17, 17.5 and 18 s. Later `coat:279` has 9 detections from 19.5-25 s, scores 0.240-0.433, first box `(0.207, 0.432, 0.457, 0.501)`, inside the desk and outside the fixtures. It is absent at 20, 22 and 24 s; the 24.5 s detection is classified as worn. | Previously every interval was at most 2 s. Missing samples at 20 and 22 s now bridge positive observations of `coat:279`. The retained interval is 19.5-24 s, duration 4.5 s. Newly caught at 19.5 s, matching the spreadsheet's personal-items violation. |
| X-1 | `handbag:69`, 19 detections from 16.5-25.5 s, scores 0.217-0.322, first box `(0.073, 0.501, 0.272, 0.578)`. A matching box already appears at 0 and 1.5 s under `handbag:1`. No counter calibration candidates exist. | Still caught only by personal items at 20 s, duration 6 s. Spreadsheet violation is manual recount/return of cash after machine counting, not personal belongings. This remains an accidental catch. |
| Х-4 / Х-47 | `handbag:1`, 34 detections from 0-22 s, scores 0.211-0.291, first box `(0.073, 0.500, 0.274, 0.579)`. No counter calibration candidates exist. It resembles the static box in X-1 and clean Х-48; identity is not established numerically. | Personal findings `0, 17.5` become `0, 8.5, 17.5` s. Still caught; `C-ID-BEFORE-CASH@66` also survives. Spreadsheet violations are cash from the previous client left out at 57 s and mixed with another client's cash at 68 s. Personal hits do not establish either violation. |
| Х-11 | `handbag:50`, 11 detections from 17.5-24.5 s, scores 0.214-0.339, first box `(0.089, 0.435, 0.270, 0.552)`. Every center lies in the calibrated counter; finding-box IoU is 0.700. | Still caught only by personal items at 20.5 s; duration increases from 3.5 to 4.5 s. Spreadsheet violation is leaving the laptop unlocked, so this is an accidental catch. |
| Х-13 | `handbag:1`, 128 detections from 0-65 s, scores 0.208-0.374, first box `(0.046, 0.370, 0.247, 0.499)`. Every center lies in the counter; first finding-box IoU is 0.975. | Findings `0, 32.5, 60.5` merge into one at 0 s, duration 65.5 s. Still caught only by personal items. Spreadsheet violation is storing cash without recount/accounting, not a personal bag. |
| Х-15 | `handbag:2`, 27 detections from 0-19.5 s, scores 0.216-0.316, first box `(0.047, 0.387, 0.252, 0.498)`. All centers lie in the counter; original finding-box IoU is 0.901. | Still caught only by personal items; fragmented intervals merge and anchor moves from 10 to 7 s, duration 11.5 s. Spreadsheet violation is leaving the collection bag unattended. The personal-item hit is accidental. |

Prompt diagnosis: `config/perception.yaml` uses generic `"a handbag"`, and
`"a coat lying on a desk"`; labels alone do not distinguish work equipment or clothing
fragments. Collection bags use separate green-cloth `bag` prompts and are not personal
items in this rule. No prompt change was claimed measurable from an unchanged cache.

**3. Every changed verdict and finding list**

Only Х-40 changes whole-video verdict: missed violation -> caught violation. No verdict
regresses. X-1, Х-4/Х-47, Х-11, Х-13 and Х-15 all stay caught.

The only other changed finding lists are Х-4/Х-47 (extra 8.5 s personal interval), Х-15
(10 -> 7 s), Х-14 (19 s interval merged into 0 s), and Х-13 (32.5 and 60.5 s intervals
merged into 0 s), as detailed above. All findings of every other enabled rule are identical
on all 40 videos. All other clips' finding lists are identical. Clean false alarms remain
Х-8, Х-14, Х-29, Х-35 and Х-48; this change does not solve them.

**4. Personal-item finding times versus organizer timestamps**

These are all violation clips hit by this rule after the change. Signed offsets are
`finding - organizer` in seconds. Timing proximity does not make an unrelated rule correct.

| Clip | Organizer | Personal-item findings | Offsets | Matches described violation? |
|---|---:|---|---|---|
| X-1 | 22 | 20 | -2 | No |
| Х-4, same cache as Х-47 | 57 | 0, 8.5, 17.5 | -57, -48.5, -39.5 | No |
| Х-47 | 68 | 0, 8.5, 17.5 | -68, -59.5, -50.5 | No |
| Х-11 | 18 | 20.5 | +2.5 | No |
| Х-13 | 47 | 0 | -47 | No |
| Х-15 | 15 | 7 | -8 | No |
| Х-40 | 17 | 19.5 | +2.5 | Yes |

**5. Files, tests, rejected alternatives and reproduction**

Files touched: `backend/f1/events.py`, `tests/test_f1_rules.py`, `REPORT-ORCH.md`,
`attempts/README.md`, and `attempts/ORCH-personal-detection-gaps/README.md`.
The shared runtime change is confined to personal-item condition lifetime in
`EventBuilder.push` and its final flush in `finish`; it reuses the previously unused
`last_personal_presence` dictionary. Calibration, `rules.py` helpers and all other event
families are unchanged.

Added 8 test cases in 3 test functions: reconnect one missing sample, expire a long gap,
keep distinct tracks separate, stop on carried/off-desk evidence with or without a preceding
gap, and exclude trailing uncertainty at expiration/end of video. An initially present
personal item still triggers. The positive gap test failed against the original code.
Two further tests caught trailing-gap duration inflation during implementation and passed
after correction.

Validation: required three test files **82 passed, 1 skipped**. The existing full-model
end-to-end test is unconditionally skipped because it requires downloaded model weights.
Ruff check and format check pass for both changed Python files. No network/VM access or
dataset image/frame access was used; the required detector tests use their synthetic fixtures.

Rejected alternatives, measured against the retained gap handling:

| Alternative | Correct | Clean false alarms | Missed | Reason rejected |
|---|---:|---:|---:|---|
| Exclude personal findings whose center is inside laptop/counter, using the existing `on_desk` fixture test | 23 | 5 | 12 | Removes all personal hits on Х-14, Х-11, Х-13 and Х-15. Х-14 still has leave-rule false alarms; Х-11/13/15 become missed violations. No clean whole-video verdict improves. |
| Remove the worn-coat test's relative-area requirement, keeping its existing >70% overlap requirement | 26 | 4 | 10 | Clears Х-35 but suppresses the true desk coat in Х-40 as well. A projected overlap with a person is insufficient evidence that a coat is worn. |

Neither alternative is in the committed implementation. No first-frame exemption was
introduced: the norm prohibits keeping belongings, including items present before recording.
Fixing work-tool semantics without losing accidental catches requires the actual cash/leave
rules to catch their own violations, or more discriminating perception.

Reproduce the retained result from the worktree root:

```bash
export API_KEY=x PYTHONPATH=.
S=/tmp/claude-1000/-home-sultanbek-projects-hackathons-datathon26/63bd15ca-5dd2-4bc8-a818-01aa3c847602/scratchpad/orch
PY=$S/venv/bin/python
$PY scripts/replay_f1.py run --cache-dir "$S/perception_cache" > /tmp/personal-after.jsonl
$PY scripts/replay_f1.py score /tmp/personal-after.jsonl --labels data/prepared/videos.jsonl
$PY -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
$PY -m ruff check backend/f1/events.py tests/test_f1_rules.py
$PY -m ruff format --check backend/f1/events.py tests/test_f1_rules.py
```

Local numeric evidence: `/tmp/personal-before.jsonl`, `/tmp/personal-after.jsonl`,
`/tmp/personal-after-score.txt`, `/tmp/personal-audit.json` (baseline),
`/tmp/personal-audit-final.json`, `/tmp/personal-fixture-candidate.jsonl`,
and `/tmp/personal-partial-coat-candidate.jsonl`. The temporary audit script is
`/tmp/personal_audit.py`; none of these generated files is committed.
