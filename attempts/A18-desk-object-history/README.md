# A18 - Desk objects by history: find items by desk change, name them by 2 agreeing clues

- **Date / who:** 2026-10-18, agent session (idea from the user, sharpened in a grilling session)
- **Status:** measured, rejected (failed the bar agreed before the run)
- **Where it ran:** offline replay on `datathon`: `scripts/replay_f1.py run --videos-dir` on the
  run-4 perception cache plus `~/data/open/videos`, CPU only; working-tree copy in `~/a18-work`
- **Models:** as A17 (no new models); desk change is plain OpenCV

## Approach

The idea: stop trusting the detector's label for small objects (cash was found in only 4 of 11
frames in A13). Track "things" on the desk instead, and decide what a thing is from its history.

`backend/f1/desk_objects.py`:

1. **Finding objects.** Crop the desk. Take the "before" picture from the emptiest moment of the
   same clip (lowest edge energy among frames with almost no one over the desk). Diff every frame
   against it, then form blobs. People's boxes, the laptop and the money counter are masked.
   Blobs are linked across frames, and a hidden frame doesn't end an object. Other clips are never
   used.
2. **Naming objects: 2 of 3 clues must agree.**
   - Origin: the zone the placing hand came from in the 3 s before the object appeared. The safe
     suggests cash or a bag, the money counter cash, the client side cash, documents or a bag.
     Already there at the start means origin unknown.
   - Counted: the money counter ran while the object lay there, or up to 10 s before.
   - Detector: the OWLv2 label on the object in at least 2 frames.
3. **Leave rules** (`rules.left_with`): when `Context.desk_objects` is set, the items come from
   desk objects. The leave logic is unchanged: the item is present at the leave and still there
   2 s later. When it's `None`, the rules work as in A17.

The bar was agreed before the run: catch at least as many violations as A17 (replay: 10 missed)
and flag fewer clean clips (replay: < 5).

## How to reproduce

```
# on datathon, with the repo tree in ~/a18-work
docker run --rm --entrypoint '' -v datathon26_work:/app/runtime:ro \
  -v ~/data/open/videos:/videos:ro -v $PWD:/work:ro -w /work -e PYTHONPATH=/work -e API_KEY=x \
  forte-cash-checker:cuda python scripts/replay_f1.py run --videos-dir /videos > a18-desk.jsonl
python scripts/replay_f1.py score a18-desk.jsonl --labels data/prepared/videos.jsonl
```

The ablation runs `logs/a18_variants.py` the same way (same mounts, `python a18_variants.py`).

## Results

Offline replay, same 40 clips, organizer labels:

| Variant | Correct /40 | Clean false alarms | Missed |
|---|---|---|---|
| A17 (flag off; identical to A17's replay) | **25** | **5** | 10 |
| **A18: 2 agreeing clues** | 22 | 6 | 12 |
| Ablation: any desk object left counts (identity ignored) | 24 | 9 | **7** |
| Ablation: detector label, only on desk-change objects | 23 | 5 | 12 |
| Ablation: one clue is enough | 24 | 9 | 7 |

Runtime: 74 s for all 40 clips on CPU (decoding included).

What changed against A17 (A18 row):

- Fixed: Х-8 (clean; a "document" in the desk corner from frame 0 is no longer flagged).
  Х-40 and Х-30 are violations now caught by `L-NO-CASH-ON-LEAVE` (origin safe + counted).
- Broke: Х-12 and Х-21, clean clips now flagged (origin counter/safe + counted). Х-26 is missed:
  desk change does find the item across the leave, but only one clue (origin safe) supports it.
  Х-20 and Х-24 are missed: the "documents left" rule can't fire, because the detector almost
  never lands on a desk-change object.

## Why it failed

- **The clues aren't independent.** "Came from the safe or counter" and "the counter ran" both
  just mean "a cash session is going on". Two of them agreeing is closer to one clue than two.
  Most objects in a cash session pick up both.
- **The origin zones are too generous.** The safe and the counter sit next to the desk, so a
  wrist path passes through them often: 51 of 191 objects got "safe" and 26 got "counter".
- **The detector and desk change rarely see the same thing.** Only 14 of 191 desk objects carry a
  detector label, so the detector clue almost never votes, and documents can't reach two clues.
- **Blob quality.** Many objects are thin strips along the desk's far edge (height ~0.01-0.02 of
  the frame). Those are people or reflections behind the desk, not items.
- **The bar was tight by design.** 4 of A17's 5 clean false alarms come from other rules
  (`W-NO-PERSONAL-ITEMS` ×3, `A-DOOR-LOCK`). Passing meant the leave rules had to drop to zero
  clean false alarms without losing a catch.

## What survives

Finding items by desk change does work for "something was left". Ignoring identity, it cuts misses
from 10 to 7, but clean false alarms rise from 5 to 9. The weak half is naming. Ideas for a next
attempt, not tried here and to be judged against a fresh bar:

- Independent clues only, e.g. hand counting motion on the object rather than the counter machine.
- Strict origin: the wrist must be inside the open safe, using the safe's open/closed state.
- A blob shape filter.
- A crop classifier trained on hand-labelled desk crops. That needs labels; A07 shows a probe on 40
  clips isn't enough.

## Logs

- `logs/a18-baseline.txt` / `.jsonl` - flag off, per clip (equals A17's `replay_fix3`)
- `logs/a18-desk.txt` / `.jsonl` - A18 per clip; the jsonl lists every desk object with its time
  span, box, origin, counted flag, detector kind and final kind
- `logs/a18-variants.jsonl`, `logs/variant_*.txt` - the ablations, from `logs/a18_variants.py`
