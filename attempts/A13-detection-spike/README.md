# A13 - Detection spike: can off-the-shelf models see the objects?

- **Date:** 2026-10-17, 10:45-10:50 UTC (the earliest experiment on `datathon`)
- **Status:** measured; it shaped the choice of OWLv2 for A01 and of a VLM questionnaire for A02
- **Where it ran:** `datathon` (L4), `~/spike_test.py`, outputs `~/spike_out/` and `~/spike_out_vlm/`
  (also in the local VM copy `archive/vm-copies/datathon/`)
- **Models:** OWLv2 `google/owlv2-base-patch16-ensemble`, Grounding DINO
  `IDEA-Research/grounding-dino-base`, Qwen2.5-VL-7B-Instruct (bf16)

## Approach

20 hand-picked frames from the open clips, each with hand-written expected answers (cash on
desk, safe open, cash bag, ID card, cup/food, coat/handbag, laptop screen state).
Path A: open-vocabulary detectors with text prompts. Path B: the VLM answers fixed
yes/no questions as JSON.

## Results (33 scored answers over 20 frames)

| Key | OWLv2 | Grounding DINO | Qwen2.5-VL-7B |
|---|---|---|---|
| cash | 4/11 | 4/11 | 4/11 |
| safe_open | 3/4 | 1/4 | 3/4 |
| bag | 3/5 | 4/5 | 5/5 |
| id_card | 1/2 | 0/2 | 0/2 |
| coat_bag | 2/3 | 2/3 | 3/3 |
| food_cup | 4/4 | 2/4 | 3/4 |
| screen | 0/4 | 0/4 | 3/4 |
| **Total** | **17/33** | **13/33** | **21/33** |
| Time per frame | 0.2 s | 0.4 s | 4.1 s |

## Logs

- `logs/spike_out/report.html`, `logs/spike_out/results.json`, `logs/spike_out/img/` - OWLv2 and Grounding DINO
- `logs/spike_out_vlm/report.html`, `logs/spike_out_vlm/results.json`, `logs/spike_out_vlm/img/` - Qwen2.5-VL
- `scripts/spike_test.py` - the script, with the 20 test frames and expected answers

## Conclusion

No model sees **cash** reliably (4/11 for all three). That's the cue most rules depend on, and
it's still the main perception gap in A01, A02 and A12. The VLM does best overall and is the
only one that reads the laptop screen.
