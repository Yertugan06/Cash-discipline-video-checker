# A25 own cash head: training underfit reduced; reject promotion

Actual offline CPU run completed in **9.301 s**, exit 0. Preregistered train-only LOCO selected **lambda 0.01**. A24 source, pins and artifacts, including bytecode, verified byte-identical before/after. No production, GPU, dependency, A23 service or LLM-context change.

| Class-balanced train-clip LOCO signed-target MSE | Loss |
| --- | ---: |
| lambda 0.0001 | 0.865905 |
| lambda 0.001 | 0.817719 |
| **lambda 0.01 — selected** | **0.761508** |
| lambda 0.1 — A24 setting | 0.911139 |

Selection plus provenance checks took 0.683 s. Each of 32 folds omitted **all six** augmentations of one of the eight training clips, fit the other 42 vectors, and evaluated only the held clip's identity. Class-balanced aggregation gave equal weight to the five positive and three negative clip classes; exact ties favor larger lambda. No probe feature, label, loss, statistic or augmentation entered selection/fitting. All fold scores/losses are in `artifacts/run-01/selection.json`.

| Fixed-threshold decisions | TP | TN | FP | FN | Unknown positive | Unknown negative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A24 train8 | 1 | 0 | 0 | 0 | 4 | 3 |
| A25 train8 | 4 | 3 | 0 | 0 | 1 | 0 |
| A24 probe4 | 1 | 0 | 0 | 0 | 1 | 2 |
| A25 probe4 | 1 | 0 | 0 | 0 | 1 | 2 |

All four probe decisions are unchanged. X4: present (+0.800403); X13: unknown (−0.002550); X33: unknown (−0.157069); X40: unknown (+0.005243). Train X26 remains unknown (+0.051562). Raw scores are **uncalibrated ridge values**, not probabilities/confidence. Unknowns came from the unchanged ±0.2 score gap; nearest-training cosine cutoff remains 0.75. Both probe negatives abstain, so zero FP does not demonstrate negative classification.

The parent requested this different preregistration because A24's **training** identities exposed underfit. We changed only regularization via the fixed grid; weighted objective, class balance, centered intercept, frozen DINOv2 and all other policy remain unchanged. A24's module is reused in an isolated process with lambda restored after each fit; no A24 file is edited. The 48 cached vectors' order was established from hash-matched original source and completed rows: eight training rows in manifest order, six variants each, identity at offset1. All eight reconstructed identity scores matched A24 within 1e-8. Four probe identities were decoded/extracted **once after selection was persisted**, with A24's exact native ROI/letterbox/CPU policy. Their recomputed A24 scores matched the saved values exactly.

Artifacts: `artifacts/run-01/head.json` (finite coefficients/intercept, 48 train-only OOD references, backbone/preprocess/source/feature/selection hashes); `selection.json` (32 folds and ordering proof); `report.json` (all12 scores and abstentions); `a24-before.json` (all-file fingerprints). `decision.json` supplies UI status **trained_not_promoted**. Exact reproducible CPU argv is `cpu-command.json`; numeric/text output is `cpu-run.log`. Execute the argv array with Python `subprocess.run(json.loads(path.read_text()))`. CUDA was hidden and CPU/BLAS/OpenCV threads capped at two; no pixels were saved/exported.

One numeric ridge/serialization/predict/OOD check passed before actual fitting; unchanged-lambda coefficients matched the original helper. Actual artifact checks confirmed 4×8 folds, 42 fit samples per fold, six omitted transforms, 3840 dimensions, 48 train-only references, chosen lambda consistency, stable head hash and A24 preservation. No broad suite or additional tuning.

**Recommendation: retain A25 as an experimental trained artifact; reject promotion.** The training fit improved, but this four-row development probe shows no decision gain. A24 probe results were already seen and all public40 influenced development; this is not blinded/new held-out accuracy. Region cash presence is not a bounding-box detector, owner or violation finding. Any LLM-context adapter requires a separate measured gate; no such adapter is included.
