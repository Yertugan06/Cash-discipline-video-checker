# A24 own cash-presence model — actually trained on CPU

The requested frozen DINOv2 + own weighted ridge head trained and persisted successfully in **34.584 s**, with exit 0. No GPU, peer code/pickle, dependency install or production change. All 12 native-source ROIs/frames were accepted; 8 designated training frames generated 48 features, and 4 probes generated identity features only. Maximum actual/requested decode difference was **0.100 s**, within the frozen 0.12 s tolerance. Backbone loading took 0.261 s; CPU feature extraction dominates the run. Torch/BLAS/OpenCV decoding were limited to two threads, with CUDA hidden.

| Frozen decision result | TP | TN | FP | FN | Unknown positive | Unknown negative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train8 identity frames | 1 | 0 | 0 | 0 | 4 | 3 |
| Probe4 identity frames | 1 | 0 | 0 | 0 | 1 | 2 |

These counts keep abstentions separate. Both probe negatives were unknown; zero false positives is **not** evidence of successful negative classification. All abstentions came from the signed-score gap, not OOD. Probe nearest-training cosines ranged 0.868–0.960, exceeding the frozen 0.75 OOD cutoff despite uncertain cash scores. The model is **not ready for promotion**. Training fit is not an accuracy gain, and all public40 influenced development.

| Probe (evaluation identity only) | Human cash label | Signed ridge score | Decision |
| --- | --- | ---: | --- |
| X4 @56 | present | +0.235859 | present |
| X13 @30 | present | −0.007195 | unknown |
| X33 @2 | not present | −0.041334 | unknown |
| X40 @18 | not present | −0.008299 | unknown |

No name or timestamp enters the learned head. They select/evaluate reviewed source frames only. Raw scores are uncalibrated ridge values, never probabilities or confidence. Region presence supplies no cash box, count, identity, ownership or legal/rule conclusion. Frame-presence supervision and an automatic workspace ROI may still disagree spatially; no human cash boxes were available and none were invented.

`PREREGISTER.md` froze the backbone revision, ROI, preprocessing, augmentation, ridge objective and thresholds before actual output. The runner uses native video SHA verification and automatically calibrated cached desk expanded 10% per side, union calibrated counter; it never selects an outcome-dependent ROI. It letterboxes the full crop to 224 using RGB(124,116,104), preserves aspect and disables processor resize/center crop. Features are CPU float32 CLS + four 8×8 quadrant means of the 16×16 DINOv2 patch grid, each L2-normalized, concatenated and L2-normalized to 3840 dimensions. All six identity/flip × brightness variants remain with the training clip.

Our head fits the preregistered class-balanced weighted-centered dual ridge objective with lambda 0.1, unregularized intercept and targets −1/+1. Only designated training features enter class counts, weighted means, coefficients or nearest-training references. Train/probe source and parent hashes are disjoint and asserted before model loading. Labels/splits came unchanged from the staged manifest; only field spellings `records`, `cash_visible`, `group_sha256` were adapted. No probe augmentation, threshold adjustment, hyperparameter search or additional fitting after results. LOCO omitted because it is optional and the first result already has high abstention.

Artifacts:

- `artifacts/run-01/head.json`: actual finite 3840-coefficient head/intercept/classes, frozen thresholds, train-only reference vectors, backbone pin, preprocess/source/train hashes. **5,351,491 bytes**, mostly the 48 numeric OOD reference vectors. SHA256 `0d8a0ebf4f0072f713954f682068257bdd7ad3b9a07feff054bb485eebc28275` (verify against `report.json` if this text is moved).
- `artifacts/run-01/report.json`: every row's actual decode time, numeric calibrated ROI, feature runtime, prediction, signed score, nearest-training cosine, abstentions and split confusions; source/runtime hashes and versions.
- `artifacts/run-01/label-manifest.used.json`: exact staged label snapshot; no pixels.
- `cpu-command.json`, `cpu-training.log`, `selfcheck-result.json`, `artifact-check.json`: exact argv and actual checks/logs.

Re-run with the same offline inputs:

```sh
python - <<'PY'
import json, subprocess
from pathlib import Path
p = Path('/home/ubuntu/workspaces/datathon26-workers/worker-2/attempts/A24-own-cash-model/cpu-command.json')
raise SystemExit(subprocess.run(json.loads(p.read_text())).returncode)
PY
```

The argv uses the existing shared/a21/visual-venv Python, shared/a23/base (declared main4a3b9ea), all40 cached Scenes, native originals, staged labels/model, `--device cpu --threads 2`, and explicit CUDA/offline/BLAS environment. DINOv2 revision is `f9e44c814b77203eaa57a6bdbbd535f21ede1415`; all downloaded config/weights/processor hashes were verified against the root's ready manifest before model loading. It writes only this attempt's JSON/text artifacts, never decoded images. Re-run overwrites `run-01`; preserve that directory or change `--out` to compare an independently authorized experiment.

Meaningful validation actually run: numeric dual-ridge fit/predict; class balance remains invariant when positive rows are duplicated; finite JSON round-trip; OOD and invalid/zero-feature rejection. Actual trained artifact validation checks dimension/classes, 48 train-only references, split disjointness, and current code/preregister/label fingerprints matching the completed run. No broad suite or GPU job. No production integration until a separate measured gate supports it.
