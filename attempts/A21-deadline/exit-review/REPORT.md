# Cashier exit review — 2026-10-18

Narrow candidate-relative fix: a cashier moving toward the calibrated door can be
localized there by a confident hand even when its hips miss the projected door polygon.
The existing movement, desk-distance, track-loss gap and exit timestamp are retained.
A newly visible overlapping track blocks this added path, because it may continue the
lost identity. No tracker, appearance matching, new threshold or rule change is introduced.

Baseline is the exact combined candidate events.py, not main 7bc47e7. SHA-256:
`d662f47fc517ecde32ba1e41f558646f8604e851795ff39418b3a5257cb15187`.
The ID/document distinction, cash reassociation/provenance, and interval evidence fixes
are preserved. Candidate-relative patch contains only the exit block and the new test.

Evidence for the missed X28 departure:

- Last accepted cashier track: person:1 at 13.5 s, hip (0.300781, 0.337649).
- Existing expanded door edge ends at x=0.297678: the hip misses by 0.003103.
- A last-frame hand reaches x=0.252061, inside the existing door-contact margin.
- Distance to the door center decreases from 0.367735 to 0.185980; the existing
  required movement is 0.040163. Desk separation is 0.092039, exceeding that guard.
- The early 7.0 s loss still lacks departure evidence and remains TRACK_LOST.
- The 14.0 s fragment person:19 has box IoU 0.295 and only one sample; it was filtered
  as glass. No identity transfer or role is invented from it.
- At the unchanged 14.0 s loss anchor the raw laptop observation is working.
  The filtered SCREEN state had remained closed since 12 s, but the current
  candidate laptop rule uses the direct nearby observation. No state is overwritten.

Counterexample checked: X12 person:1 disappears at 33.5 s, while person:32 appears
at 34.5 s with overlapping geometry and continues moving. The added hand path is
blocked there; the existing later exit remains 37.5 s. This is why a hand-only
prototype was not retained.

| Clip | Cache | Cashier EXIT anchors before | After | Laptop rule before → after |
| --- | --- | --- | --- | --- |
| 11 | fresh-d2 | [11.5, 17.0, 20.5] | [11.5, 17.0, 20.5] | [] → [] |
| 12 | legacy local | [37.5] | [37.5] | [] → [] |
| 19 | legacy local | [] | [] | [] → [] |
| 20 | fresh-d2 | [] | [] | [] → [] |
| 21 | fresh-d2 | [] | [] | [] → [] |
| 22 | fresh-d2 | [17.5, 19.5] | [17.5, 19.5] | [] → [] |
| 23 | fresh-d2 | [14.5] | [14.5] | [] → [] |
| 24 | legacy local | [10.5] | [10.5] | [] → [] |
| 25 | legacy local | [27.5] | [27.5] | [] → [] |
| 26 | legacy local | [15.0] | [15.0] | [] → [] |
| 27 | fresh-d2 | [] | [] | [] → [] |
| 28 | legacy local | [] | [14.0] | [] → [14.0] |
| 29 | legacy local | [13.5] | [13.5] | [] → [] |
| 39 | legacy local | [] | [] | [] → [] |

Only X28 changes; the other 13 requested comparisons retain their departure events
and laptop-rule findings. Coverage, sessions, cash/ID evidence events, and other
non-departure/non-away events remain identical in these replays. This is not a
40-clip score or new human event labeling.

Actual validation:

- `RULE_SCOPE=detector .venv/bin/pytest -q tests/test_f1_exit_review.py`: 8 passed in 0.32 s.
- One focused parametrized test checks hand/hip departure, stationary/seated loss,
  safe work, uncertain hands, movement away from the door, overlapping replacement
  track and recording cutoff.
- `RULE_SCOPE=detector .venv/bin/python /tmp/a21-exit-review/replay_comparison.py`:
  numeric replay of all 14 requested clips against the same rules/config snapshot.
- Ruff check/format and `git diff --check`: passed.
- `git -C /tmp/a21-exit-review/apply-check apply --check /tmp/a21-exit-review/candidate-relative.patch`:
  patch application checked against a clean copy of the combined candidate.

Initial focused test failure: its synthetic scene omitted the calibrated door polygon;
the fixture was corrected. No remaining test failures. The hand-only prototype also
changed X12, so the continuity ambiguity guard was added before delivery.

Changed repository files: backend/f1/events.py and tests/test_f1_exit_review.py only
for this followup. Recognition experiment files, rules, configuration and dependencies
were not edited. No GPU, service, download, image viewing or media decoding was used.

Replay rules snapshot SHA-256: `cf5d6ca4c242170675d3aa75d13f80d937e73b934c584387263078e37eecb714`.
Raw numeric paths, event logs, evidence and before/after results: comparison.json.
Use candidate-relative.patch for integration; its baseline hash above identifies
the combined source. No files were committed.

Skipped: broad suites, GPU work and full fresh-40 replay. Risk: fresh X28 and seven
other requested caches were not present on this VM; fresh all-40 validation remains
the orchestrator's integration step. Existing duplicate exits and missing cashier
calibration in some other clips were preserved, not claimed fixed.
