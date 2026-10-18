# A27 - Zero-shot cash detectors with commercial-use licenses

- **Date / who:** 2026-10-18, agent (Claude) with the user marking boxes
- **Status:** measured; runtime unchanged
- **Where it ran:** `datathon` (L4, shared with the live checker), `~/a27/` scripts, `~/a27_out/` outputs,
  `~/dt26-validation/.venv` (torch 2.11, transformers 5.20.1), no installs
- **Models:** `google/owlv2-base-patch16-ensemble` (runtime model), `google/owlv2-large-patch14-ensemble`,
  `openmmlab-community/mm_grounding_dino_large_all` (all Apache-2.0). `facebook/sam3` was planned but
  not run: the repo is gated (needs an HF token with the SAM License accepted).

## Approach

Rules frozen before any output in `PREREGISTER.md`. The 12 frame-presence labels from A24
(7 cash visible, 5 not), A13's three cash prompts, each prompt in its own forward pass, on the full
frame and on four overlapping 60% tiles. Frame score = best box score. Then the user marked each
model's top box (28 boxes, 12 frames) as cash / not cash / unclear on a review page on the VM
(`scripts/label_server.py` + `scripts/label_page.html`), with model names and scores hidden.
Frames never left the VM.

## How to reproduce

```sh
# on datathon, in ~/a27 with run.py, label_server.py, label_page.html, score_boxes.py,
# diag_query_competition.py, label-manifest.json (A24) and config/perception.yaml
PY=~/dt26-validation/.venv/bin/python
$PY run.py --manifest label-manifest.json --videos ~/data/open/videos --out ~/a27_out
$PY label_server.py --manifest label-manifest.json --videos ~/data/open/videos --out ~/a27_out
#   locally: ssh -N -L 8200:127.0.0.1:8200 datathon -> http://localhost:8200
$PY score_boxes.py --out ~/a27_out
$PY diag_query_competition.py --manifest label-manifest.json --videos ~/data/open/videos \
    --out ~/a27_out --perception perception.yaml
```

## Results

Frame level (pre-registered metrics; AUROC over 7 x 5 pairs):

| Model | AUROC full | AUROC full+tiles | Margin full+tiles | TP/FN/TN/FP at default thr, full+tiles | s/frame (15 passes) |
|---|---|---|---|---|---|
| OWLv2-base (thr 0.15) | 0.943 | 1.000 | +0.012 | 7/0/4/1 | 2.7 |
| OWLv2-large (thr 0.15) | 1.000 | 1.000 | +0.195 | 7/0/5/0 | 12.6 |
| MM-Grounding-DINO-large (thr 0.30) | 0.743 | 0.314 | -0.225 | 7/0/0/5 | 22.0 |

Human box review of each model's top box (`logs/box-score.json`):

| Model | Top box on cash, cash frames | Wrong box above threshold |
|---|---|---|
| OWLv2-base | 7/7 | 1 (X-40, coat/handbag frame, 0.152) |
| OWLv2-large | 7/7 | 0 |
| MM-Grounding-DINO-large | 0/7 (6 not cash, 1 unclear) | 12/12 |

No cash was drawn as missed by all models.

Post-hoc diagnostic, not pre-registered (`logs/diag-query-competition.json`): A13 reported OWLv2
cash TP 0/7. On the human-confirmed cash box, OWLv2-base's banknote score is 0.07-0.39, but when all
of A13's 19 queries run together each box takes its best query, and "id card" / "plastic card"
wins on all 7 cash boxes. Repeating this with the runtime's own `object_prompts`, 640 px and
threshold 0.12 (mirroring `backend/f1/perception.py` `objects()`, full frame only, no desk crop):
the cash box is labelled `id_card` in 4/7 frames, `cash` in 1/7, and gets no box in 2/7.

## Logs

- `logs/results.json` - every view x prompt best score and box per frame and model
- `logs/summary.json` - pre-registered frame-level metrics
- `logs/box-labels.json` - the user's box marks (also on the VM, with a timestamped backup)
- `logs/box-score.json` - per-model scoring of the marks
- `logs/diag-query-competition.json` - A13-query and runtime-prompt competition diagnostic
- VM only: `~/a27_out/img/` overlay images (frames stay on the VM)

## Conclusion

- The cash gap in A13 was mostly how labels were assigned, not what OWLv2 can see. Asked about
  banknotes alone, OWLv2-base already puts its top box on cash in 7/7 frames.
- The live runtime has the same pattern: one OWLv2 pass with all object prompts and one label per
  box turns most cash into `id_card`, which also feeds `ID_SHOWN` events. Fixing label competition
  (score cash prompts on their own or allow several labels per box) is the cheapest next step, ahead
  of any new model. Measure it with a full replay before changing runtime.
- OWLv2-large is the better model here (clear margin, no wrong box), at about 4.6x the cost.
- MM-Grounding-DINO-large is not usable for cash on these clips.
- Limits: 12 frames, all already seen in A13/A24/A25; one reviewer; top box only (not every
  cash instance); frames are A13's hand-picked ones. Not a held-out accuracy claim.
- Label page bug on first use: the server did not URL-decode `@` in frame keys, so the first pass
  of marks returned 404 and was lost; fixed, re-marked, and the page now keeps and retries failed saves.
