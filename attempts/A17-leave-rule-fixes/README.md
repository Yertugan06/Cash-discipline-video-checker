# A17 - Leave rules: laptop is not a tablet, away = out of laptop reach, item must stay

- **Date / who:** 2026-10-17, agent session
- **Status:** live on `datathon` together with A16 (cashier side from the lone person); run 4 done
- **Where it ran:** offline replays with `scripts/replay_f1.py` on the run-3 perception cache,
  then a live 42-file run through the gateway
- **Models:** as A14 (no new models)

## Why

With A16 the cashier is found on both camera directions, which turned on the leave rules and
produced their own false alarms (`L-NO-DOCS-ON-LEAVE`, `L-NO-CASH-ON-LEAVE`). In
`logs/before_desk_items_at_each_leave.txt` (the items on the desk at every cashier leave):

1. The "tablet" on the desk is the laptop itself: OWLv2's "a tablet computer" prompt
   matches the laptop, with the same box (e.g. Х-45 `tablet:1 [0.13,0.44,0.28,0.50]`).
2. Х-10, Х-8: `WORKSTATION_AWAY` at 1.0 s with the cashier seated. The old test was "near the
   door zone or outside the cashier zone, and box centre > 0.2 from the laptop". With a camera
   facing the cashier, the glass door is right behind them in the image.
3. Clean twins such as Х-25: the item is on the desk when the cashier stands up, and they take
   it with them.

## Changes

1. `rules.Context.on_desk`: an item whose centre lies on the calibrated laptop or counter is
   that fixture, not an item on the desk.
2. `events.EventBuilder.push`: the cashier is away when their hips are farther from the laptop
   than `calibration.LAPTOP_REACH`, the same reach that defines "working at the laptop" in A16.
3. `rules.left_with`: an item counts only if it is still on the desk `LEFT_BEHIND_SEC` (2 s)
   after the leave.

Each change has a test that fails without it (checked by removing the fix).

## Results

Offline replay, same 40 cached clips:

| Variant | Correct | Clean false alarms | Missed |
|---|---|---|---|
| near/far (A14, live before this) | 22 | 5 | 13 |
| lone-person split (A16) | 20 | 13 | 7 |
| + 1. laptop is not a tablet | 23 | 7 | 10 |
| + 2. away = out of laptop reach | 24 | 6 | 10 |
| + 3. still on the desk 2 s later | **25** | **5** | **10** |

Live run 4, 42 files (the gateway scores against the organizer labels; saved as
`run4-leavefix`, `logs/live_run4.txt`):

| Run (42 files) | Match label | Clean false alarms | Missed | Worst runtime |
|---|---|---|---|---|
| before-glass-fix (A12 code) | 25/42 | 12/20 | 5/22 | - |
| run3-nearfar (A14) | 23/42 | 6/20 | 13/22 | 146.6 s |
| **run4-leavefix (A16 + A17)** | **26/42** | **6/20** | **10/22** | 144.4 s |

The live verdicts equal the offline replay on all 42 files.

Remaining clean false alarms after 3: `W-NO-PERSONAL-ITEMS` (Х-14, Х-35, Х-48; objects
already on the desk at 0 s), `A-DOOR-LOCK` at 0 s (Х-29), and one `L-NO-DOCS-ON-LEAVE`
(Х-8: a "document" lying in the desk corner from the first frame).

## Logs

- `logs/before_desk_items_at_each_leave.txt` - the diagnosis
- `logs/replay_fix{1,2,3}.txt` / `.jsonl` - per clip findings for each step
- `logs/live_run4.txt` - live run 4 per file
- `/compare` on the gateway: runs `replay-leavefix` and `run4-leavefix`
