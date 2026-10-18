# A27 - frozen before any output, 2026-10-18

Question: does a stronger open-vocabulary detector with a commercial-use license see cash
where OWLv2-base did not (A13 re-score: 0/7 cash-positive frames)?

## Frames and labels

The 12 frame-presence labels in `attempts/A24-own-cash-model/data/label-manifest.json`
(7 cash visible, 5 not), all used. No model is fitted, so the train/probe split is not used.
These frames and A13's prompts were already seen in A13/A24/A25; this is not a held-out test.
Labels are frame presence only, so a high score does not prove the box is on the cash.

Videos are resolved by `video_sha256` in `~/data/open/videos` on `datathon` (file names mix
Latin and Cyrillic X). Frames are decoded with OpenCV seek to `t` seconds, as in A13.

## Models (all with a commercial-use license)

| Key | Checkpoint | License |
|---|---|---|
| `owl-base` | `google/owlv2-base-patch16-ensemble` (the runtime model, baseline) | Apache-2.0 |
| `owl-large` | `google/owlv2-large-patch14-ensemble` | Apache-2.0 |
| `mmgdino-large` | `openmmlab-community/mm_grounding_dino_large_all` | Apache-2.0 |
| `sam3` | `facebook/sam3` (gated; runs only if access is granted) | SAM License (commercial allowed, use restrictions) |

## Prompts and views

Prompts are A13's cash prompts, unchanged: `banknotes`, `stack of paper money`, `bundle of cash`.
Each prompt runs in its own forward pass. Views: the full frame, and four overlapping tiles
(each 60% of width and height, at offsets 0 and 40%) for small objects.

## Scores

Per frame, per model: score = max over prompts and boxes of the model's own box score
(OWLv2: sigmoid class logit; MM-GDINO: post-processed box score at threshold 0;
SAM 3: instance score at threshold 0). Two variants: `full` (full frame only) and
`full+tiles` (max over all five views).

## Metrics (fixed now, no tuning after results)

1. Primary: AUROC of the frame score over 7 positives x 5 negatives (35 pairs), per model and
   variant. With 12 frames this is a coarse check: one swapped pair moves AUROC by 0.029.
2. Margin: lowest positive score minus highest negative score (positive = cleanly separable).
3. TP/FN/TN/FP at each model's default threshold: OWLv2 0.15 (A13), MM-GDINO 0.30 (A13's
   GDINO), SAM 3 0.5 (HF example default).

No prompt, threshold, tile or checkpoint change after seeing outputs. A model is worth a
follow-up (box labels and a real test) only if it beats `owl-base` on AUROC and gets at least
4/7 positives at its default threshold with at most 1/5 false positives.

## Data handling

Runs on `datathon` with the existing `~/dt26-validation/.venv` (torch 2.11, transformers 5.20.1),
no installs. Overlay images stay on the VM for human review only; they are not sent to any
cloud AI tool. Only numbers and box coordinates are copied into this folder.
