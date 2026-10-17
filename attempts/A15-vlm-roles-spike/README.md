# A15 - Spike: person roles and situation from a local VLM

- **Date / who:** 2026-10-17, agent session (asked for by the user after A14)
- **Status:** measured; zero-shot single-frame roles rejected
- **Where it ran:** `datathon` (L4), throwaway container from `forte-cash-checker:cuda`, local
  weights only (`HF_HUB_OFFLINE=1`), run-3 traces from A14 for the person boxes
- **Models:** Qwen2.5-VL-7B-Instruct (Apache-2.0), bf16, transformers 4.57.3, greedy decoding

## Approach

Idea: instead of geometry (A14's near/far split), read each person's role and the situation
(client service / cash collection / walk-through / cashier alone) from the image, so any camera
angle works. 10 clips (X-2, 3, 13, 14, 17, 19, 30, 33, 39, 46), 4 frames each (the frame with
the most person boxes in each quarter of the clip). Every person box F1 found, including the
ones A14 filters as glass, is drawn with a number. The model returns JSON:
role/action per number plus the situation (prompt in `scripts/role_spike.py`).

## How to reproduce

See the docstring of `scripts/role_spike.py` (needs `scripts/clips.json`, which maps clips to
run-3 job ids). `scripts/make_sheets.py <out dir>` draws the answers back onto the frames.

## Results

| Check | Result |
|---|---|
| Frames / JSON parse failures | 40 / 0 |
| Time per frame | median 6.4 s, max 11.3 s; peak GPU 16.8 GB |
| Boxes answered | 83 of 98 (15 boxes skipped, mostly small glass ones) |
| A14 glass boxes called `outside_or_reflection` | 17 of 37 |
| **Cashier picked correctly in frames with cashier + another real person** | **5 of 21**, judged by eye on the sheets |
| Cash collection recognised (X-17, collector with the green bag at 4 s) | yes |

The cashier/client mistake is systematic, not noise. When the cashier sits with their back
to the camera and the client faces the camera across the desk (X-2, X-3, X-19, X-39, X-17),
the model calls the person facing the camera the "cashier" in most frames. Example: X-19, all
4 frames. In X-30 (another layout) it calls the outsider the cashier. With two people, 5/21 is
worse than a coin flip.

## Logs

- `logs/results.jsonl` - per frame: boxes, F1 roles, parsed VLM answer, raw text, seconds
- `logs/sheets/X-*.jpg` - 4 frames per clip, each box tagged `number:VLM role`, MISSING = skipped

## Conclusion

A single frame does not hold the information that decides the role. Who works at the desk vs
who came in to be served is a matter of *behaviour over time*: who was in the room from the
start, who came in through the door, who sits at the laptop seat across the clip. A zero-shot
VLM looking at one frame falls back on a stereotype (person facing the camera = teller). This
agrees with A08: zero-shot VLM judgement does not hold up on these clips.

Not tried here: several frames or a short clip per question, or a prompt that describes the
layout (but that brings the camera-angle assumption back). The temporal cues ("entered through
the door", "present from the first frame", "where the person sits most of the clip") already
exist in the F1 tracks and events without a VLM.
