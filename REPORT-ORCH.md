# Client-session rules - orch/sessions

1. **Before and after**

Before, reproduced from this worktree with cached perception:

```json
{"videos": 40, "correct": 25, "clean_false_alarm": 5, "missed": 10, "outsider_on_clean": 0}
```

After:

```json
{"videos": 40, "correct": 28, "clean_false_alarm": 5, "missed": 7, "outsider_on_clean": 0}
```

Three additional violations caught, with no regressed verdicts. The score counts unique hashes;
X-4/X-47 and X-5/X-48 are duplicate pairs, and the scorer uses the last label for each hash.
These are results on the supplied 40 cached clips, not an unseen-camera evaluation.

2. **Targets and cached evidence**

Read the complete target rows in `data/Таблица_нарушений.xlsx`, sheet `Нарушения`, and the
clean descriptions in `Без нарушений`. No dataset video or image was opened or decoded;
no network, VM, GPU inference, or new perception was used.

| Clip | Cached evidence | Change and result |
|---|---|---|
| X-2 | 34 samples; cashier `person:1` in all 34; client `person:5` in 24, first seen at 4.0 s. Entry and client session are recognized. Cash, bundles, and ID cards: **0 samples each**. Documents: 11 samples, only 0-5 s. No counter was calibrated. | Still missed. The team describes cash acceptance at 10 s, but the cache contains no cash detection or cash handover. Neither a missing ID box nor client posture proves that cash was accepted. No substitute signal was invented. |
| X-18 | 45 samples; cashier `person:2` in all 45; client 1 `person:7` in 30; client 2 `person:24` in 13 consecutive samples from 16-22 s. Cash/bundles: 0. One ID-card track appears in 24 samples from 9.5-22 s; the only ID handover is cashier to client 1 at 14.5 s. It does not show the second client's document transfer described at 20-21 s. | `A-SECOND-PERSON` now also checks sustained simultaneous service at the desk, using client-side roles and hands within the existing desk-contact margin, with collectors excluded. Both clients qualify continuously at 19.5-22 s; the event starts at **19.5 s**, confirmed at 20.5 s. Caught. A short disappearance of client 1 no longer creates a second session backdated to 2.5 s. |
| X-38 | 118 samples; cashier `person:2` in all 118. Original calibration has **0** lone-person samples with hips inside laptop reach, but **8** with hands reaching the laptop. Client 1 is tracked through 27.0 s, with exit anchored at 27.5 s; the next client enters at 32.0 s. Cash appears in **38/118** samples, starting at 27.0 s; `cash:1` remains tracked through 41.0 s. ID cards: 58 samples; documents: 26. | Hands can establish the cashier side when hip distance cannot. Cash first seen at 27.0 s is then assigned to the first session. It is on the desk at 31.5 s and visibly remains when session 2 starts. The existing `S-CLEAN-DESK-HANDOVER` rule fires at **32.0 s**. The second client's standing/seated tracks, `person:64` and `person:73`, are associated within that session. Caught. |
| X-34 | 35 samples; cashier `person:1` in all 35; client `person:3` in 25 samples through 14.5 s. Original hip-based orientation has **0** qualifying lone samples; hand contact supplies **5**. Cash/bundles/ID cards: 0; document: one sample at 0 s. Counter states: 10 running, 17 idle, 8 unknown. Eight consecutive running samples cover 13.0-16.5 s. Stable `COUNT_START` is anchored at 13.0 s. | Correct orientation opens the client session. The client visibly moves away from the desk, and confirmed exit is anchored at **15.0 s**. `C-COUNT-BEFORE-EXIT` accepts an unfinished, observed counter run tied to this session as positive counting evidence, even without a banknote box. No count completion or interruption precedes exit. Caught. |
| X-4 / X-47 | Same cache: 145 samples; cashier in all 145. Cash appears in 20 samples at 57.0-62.5 and 63.5-67.0 s; ID cards: 0; document: one sample at 0 s. Client-to-cashier cash handover remains at 66.0 s. | **C-ID-BEFORE-CASH at 66.0 s is preserved.** Client track pairs 3/9 and 70/80 now belong to two sessions instead of four. Caveat: the spreadsheet describes leftover/mixed cash, and an actual card display is missing from perception. This retained ID finding does not establish that the spreadsheet's ID procedure was violated. |

3. **Other clips and clean controls**

No other clip's verdict changed. More strongly, every kept rule ID and timestamp outside
X-18, X-38, and X-34 is identical before and after. X-2 remains missed.

Each of the following 19 unique clean clips has **0 findings before and 0 after** from
`C-ID-BEFORE-CASH`, `A-SECOND-PERSON`, `S-CLEAN-DESK-HANDOVER`, and `C-COUNT-BEFORE-EXIT`:

X-3, X-5/X-48, X-8, X-10, X-12, X-14, X-16, X-19, X-21, X-23, X-25, X-27, X-29,
X-31, X-35, X-37, X-39, X-43, X-45.

Relevant controls: X-19 resolves to two sequential sessions; X-5/X-48 keeps two sessions
despite the second client's sitting track change, preventing a false count-at-exit finding.
X-37 gains roles but its client never exits. X-39 gains roles and two sessions; its one cash
sample at 9.0 s does not support leftover cash at the next session. X-35 still lacks enough
lone-workstation evidence for roles. All four remain free of assigned-rule findings.
The five existing whole-video clean false alarms remain X-8, X-14, X-29, X-35, and X-5/X-48.

4. **Assigned-rule hits versus organizer timestamps**

| Clip | Rule | Finding | Organizer | Difference |
|---|---|---:|---:|---:|
| X-18 | A-SECOND-PERSON | 19.5 s | 20 s | -0.5 s |
| X-38 | S-CLEAN-DESK-HANDOVER | 32.0 s | 33 s | -1.0 s |
| X-34 | C-COUNT-BEFORE-EXIT | 15.0 s | 13 s | +2.0 s |
| X-47, duplicate of X-4 | C-ID-BEFORE-CASH | 66.0 s | 68 s | -2.0 s |
| X-4, same cache | C-ID-BEFORE-CASH | 66.0 s | 57 s | +9.0 s |

These are all assigned-rule hits on violation caches. The last two rows describe one hit
against two organizer annotations. The three new findings are within 2 s of their labels.

5. **Implementation, checks, and rejected approaches**

Files touched:

- `backend/f1/calibration.py`: use existing laptop hand-contact evidence when there are
  insufficient lone-person hip-reach samples; preserve an already established anchor.
  Save the observed working position and share the pre-existing 0.08 hand margin with events.
- `backend/f1/vision_types.py`: optional internal `Scene.cashier_position`; old cache payloads
  remain valid. This is the only added scene field.
- `backend/f1/events.py`: add client track aliases, short-gap/overlapping-box association,
  and `SESSION_CLIENT_REASSOCIATED`. Confirm client exits using visible departure from the
  desk, rather than disappearance inside a projected door box. A later distinct client can
  close an uncertain session with `SESSION_LOST`, which is not a confirmed exit. Reset
  returning clients' entry spans so new sessions are not backdated. Emit debounced
  `SECOND_CLIENT_AT_DESK`. For layouts established through distant hand reach, measure
  cashier departure from the calibrated working position to prevent new leave-rule alarms.
- `backend/f1/rules.py`: consume simultaneous-service events; preserve client membership
  across track aliases for ID and second-person checks; recognize a still-running counter
  at confirmed exit. `S-CLEAN-DESK-HANDOVER` itself is unchanged.
- `tests/test_f1_rules.py`: eight new test functions, **16 cases**, covering service versus
  waiting/brief overlap/collectors, two camera directions, stable workstation anchors,
  actual cashier movement, running/completed/interrupted/other-session/repeated counts,
  client track changes with cash provenance and ID/second-person membership, real re-entry,
  and stale sessions.
- `REPORT-ORCH.md`, `attempts/ORCH-client-sessions/README.md`, `attempts/README.md`: results
  and history entry. No configuration, generated knowledge, or changelog was edited.

Shared merge surface is limited to calibration, the optional scene field, session/exit and
workstation event construction, and the two rule membership checks. Consumers of session
identity should use `session_client_ids()`; `client_id` identifies the current track and
`client_ids` retains its observed aliases. Threshold values are unchanged: existing
hysteresis, hand-contact/reach margins and motion tolerance are reused. Reassociation's
time bound adds one sampling interval to the existing exit gap to cover sampling uncertainty.

Validation actually run:

- Required command: `pytest -q -rs tests/test_f1_rules.py tests/test_f1_detector.py
  tests/test_desk_objects.py`: **90 passed, 1 skipped**. The existing model-dependent
  end-to-end detector test is skipped; GPU perception was not tested.
- `ruff format` on the five changed Python files; `ruff check` and `ruff format --check`
  on all `backend/f1` files plus the three requested test files: pass, 12 files formatted.
- Full-repository Ruff check: **480 existing errors in 35 untouched files**; none in changed
  files. Full-repository format check reports 39 untouched files needing formatting.
- `git diff --check`: pass. Full cached replay before and after: 40 clips each.
- Positive regression tests were observed failing before the fixes. Additional isolated
  mutation checks also failed when anchor preservation and stale-session handling were removed.

Trials that were rejected or refined:

- Hip-only orientation cannot recover X-34/X-38: neither has a qualifying lone hip sample.
- Merely enabling hand-based orientation made the seated cashier appear permanently away
  in X-39 and exposed a stale-session second-person false alarm there. The calibrated
  working anchor and session lifecycle fixes remove both.
- Extending count-at-exit without fixing sitting track changes produced a new assigned-rule
  false alarm at 67.5 s in clean X-5/X-48. Exit motion and session continuity remove it.
- Mixing all hand-contact positions into established anchors, or using every cashier's
  first assigned position as an away anchor, removed X-20's baseline catch. Both were
  rejected. Established hip-based calibration and its leave behavior are preserved.
- X-2's cash signal is absent. Lower thresholds, posture-based cash guesses, and labeling
  an undetected object were not used.

Residual limits: box overlap and short temporal continuity support track association but
do not establish a person's identity. Second-person service uses sustained desk proximity
of hands, not a newly detected document transfer. X-2 requires better cash perception;
X-4/X-47 still has missing ID evidence. No unseen-video accuracy claim is made.
