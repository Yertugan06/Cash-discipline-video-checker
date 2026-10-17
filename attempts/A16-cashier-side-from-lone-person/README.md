# A16 - Cashier side learned from the lone person at the workstation (offline)

- **Date / who:** 2026-10-17, agent session
- **Status:** measured offline, then deployed with A17 (live run 4)
- **Where it ran:** `datathon`, `scripts/replay_f1.py` on the run-3 perception cache (no GPU)
- **Models:** none new (A14 perception)

## Approach

The user pointed out that any fixed split (A14's desk->laptop or near/far) bakes in a camera
angle. A15 showed a single-frame VLM cannot tell the cashier from the client. Behavioural cue
instead: clients and collectors come in while the cashier is there, so **a person alone in the
room near the laptop is the cashier**. `calibration.orient_cashier_side` takes the median hip
point over frames with exactly one non-glass person within `LAPTOP_REACH` of the laptop (at
least 3 such frames), then splits the room along the desk's long axis with the cashier on that
side. With no such frames it leaves the zones uncalibrated (role rules off) and warns.
`calibration.behind_glass` is now the one glass check used by orientation and the event builder.

## Results (offline replay, 42 files, also on `/compare` as `replay-*`)

| Split | Match label | Clean false alarms | Missed |
|---|---|---|---|
| near/far (A14 live; replay equals run 3 exactly) | 23/42 | 6/20 | 13/22 |
| nearest person to laptop (A14 learned) | 22/42 | 14/20 | 6/22 |
| **lone person at the workstation (this)** | 21/42 | 14/20 | 7/22 |

Per clip (`logs/side_per_clip.txt`): the cashier sits on the **far side, facing the camera**
in many open clips (Х-10, Х-45, Х-43, Х-8, Х-12, Х-14, Х-44, Х-46, ... see the two frames in
`logs/`). Near/far gets these backwards. It scored better only because, with the side
flipped, the real cashier is never found, so the leave/workstation rules stay off. The
lone-person split finds the cashier on both kinds of camera, which turns those rules on and
exposes their own false alarms (`L-NO-DOCS-ON-LEAVE`, `W-NO-PERSONAL-ITEMS@0.0`). No side
found for Х-35, Х-37, Х-38, Х-39 and Х-34: nobody is ever alone at the laptop.

## Conclusion

Better roles do not raise the score yet. The bottleneck has moved to the leave rules (when
the cashier counts as "away") and to static desk objects counted as personal items. Next:
fix those on the replay, scored on `/compare`, before deploying this split.
