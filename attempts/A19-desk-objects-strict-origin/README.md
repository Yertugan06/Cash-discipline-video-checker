# A19 - A18 with strict origin and a blob shape filter

- **Date / who:** 2026-10-18, agent session
- **Status:** measured, rejected (failed the pre-registered bar)
- **Where it ran:** offline replay on `datathon`, same setup as A18
- **Models:** as A18

## Pre-registered (written before the run, not changed afterwards)

Only the two fixes named in A18's "Why it failed" that don't need new labels or models:

1. **Strict origin.** "Safe" now needs a wrist *inside* the safe box (no margin) at a moment when
   the safe's stable state is open (`SAFE_OPEN` in the event log). "Counter" needs a wrist inside
   the money counter's box, again with no margin. A18 used a 0.02 margin and ignored the safe's state.
2. **Blob shape filter.** Drop blobs with a side shorter than 6 px in the 320 px-wide desk crop,
   or longer than 6 times their width (or the reverse). These are the thin strips along the desk's
   far edge.

Everything else is as in A18: the 2-of-3 clue rule, the counted clue and the detector clue.

**The bar (same as A18):** offline replay on the 40 clips against the organizer labels. It must
miss no more than A17 (10) and flag fewer clean clips than A17 (< 5). One run, no tuning after
it. All 40 clips were already seen in A18, so even a pass would only earn a run on new clips, not
a deployment.

## Results

One run, offline replay, the same 40 clips:

| Variant | Correct /40 | Clean false alarms | Missed |
|---|---|---|---|
| A17 | **25** | 5 | **10** |
| A18 | 22 | 6 | 12 |
| **A19** | 22 | 5 | 13 |

The bar was missed <= 10 and clean false alarms < 5, so A19 fails both.

Compared with A18, only two clips changed. Х-21 (clean) is no longer flagged, and Х-40 (violation)
is no longer caught: both had relied on a hand "from the safe".

What each fix did across the 184 desk objects (A18: 191):

- Strict origin worked as designed. Objects "from the safe" fell from 51 to 7, and those
  objects now count as "from the cashier's side". "From the counter" stayed at 26: the money
  counter sits on the desk, so hands are on it during any cash work.
- The shape filter removed only 7 objects (191 -> 184); why it misses most edge strips was not checked.

## Conclusion

Naming desk items from their history doesn't beat the detector's labels with the clues we have.
Every way of tightening the clues trades a caught violation for a clean clip, and the totals stay
inside the ±2-clip tie band from the pre-registration. Changing more thresholds on these 40 clips
would only fit noise. What's left of this idea needs new information, not tuning:

- Hand-labelled desk crops (cash, document, personal item, nothing) for a small classifier,
  scored on clips it wasn't built on.
- New clips to test "any item left" (A18 ablation: 7 missed, 9 clean false alarms) against.

## Logs

- `logs/a19-desk.txt` / `.jsonl` - per clip findings and desk objects (same format as A18)
