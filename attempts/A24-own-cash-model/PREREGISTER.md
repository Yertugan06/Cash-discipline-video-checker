# A24 own cash-presence head — frozen before outputs

2026-10-18, before feature extraction or fitting. Scope: region cash presence, not a box detector, ownership model or rule/verdict change. All 40 public clips influenced development. Four probe rows are a development diagnostic only.

Frozen backbone: local `facebook/dinov2-base`, revision `f9e44c814b77203eaa57a6bdbbd535f21ede1415`, weights SHA256 `d73036b56966966d07975d696bde331762f37297e2f095de8cea0040c3aa0841`; CPU float32, eval/inference mode, two Torch/BLAS threads, CUDA hidden, offline safetensors. Pin exact download manifest/config/weights hashes in artifact. Features: CLS and four spatial quadrant patch means, each independently L2-normalized, concatenated then L2-normalized; 3840 dimensions.

ROI: calibrated desk expanded by 10% of its width/height on each side, clipped to native frame bounds; union with the calibrated counter when present. No annotation boxes or outcome-dependent crop. Missing/invalid geometry yields unknown and excludes that row from fit. Native decoded frame's video SHA and actual decode time must match the request (0.12 s tolerance). No images written. Whole crop letterboxed to 224×224 with neutral RGB(124,116,104), aspect preserved, bilinear resizing; processor resize and center crop disabled.

Exactly eight designated training source rows, four designated probe rows. Train augmentation: original and horizontal flip, each at brightness 0.9/1.0/1.1, generated before letterbox; six samples per eligible train row. Probe uses identity only. All transforms stay with the source clip. Verify train/probe video/parent hash disjointness; no probe features, augmentation, class counts, means, coefficient fitting or OOD references enter training.

Fixed class-balanced weighted ridge objective: sum_i a_i(y_i − x_i·w − b)^2 + 0.1||w||², a_i=1/(2*n_class), y∈{-1,+1}. Weighted feature/target centering, unregularized intercept, dual N×N solve. No sklearn, pickle, parameter search or threshold tuning. Export finite JSON coefficients/intercept, classes `[not_detected,present]`, source/preprocess/pin/train-group hashes, and train-only normalized reference features for nearest-train cosine.

Decision: nearest-train cosine <0.75 → unknown/OOD; otherwise signed score ≥0.2 → present; ≤−0.2 → not_detected; intermediate → unknown. Raw ridge scores are uncalibrated, never probabilities or confidence. Not-detected is limited to this model/ROI, never proof of physical absence. Report train/probe confusion counts, per-row scores and abstentions separately. Training fit is not an accuracy gain. No production integration or 40-clip/held-out claims. Optional LOCO omitted unless justified after the first actual result.

Validation: one small numeric fit/predict plus JSON round-trip selfcheck; actual CPU extraction/fit after staging. Model/data unavailable paths must fail explicitly, with a progress checkpoint. No GPU lock needed for CPU-only work and no effect on concurrent A23 GPU jobs.
