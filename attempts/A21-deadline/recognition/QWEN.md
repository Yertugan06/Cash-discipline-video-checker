# Frozen Qwen3-VL-4B presence comparison

GPU_RUN_READY. No Qwen CUDA inference was executed by this worker. Production stays
unchanged. The orchestrator's completed OWLv2 GPU result is 5 cash TP / 2 FN / 0 FP /
4 TN for both full+desk and full+desk+640 tiles; tiling added no cash recall.

`qwen-manifest.json` was frozen before Qwen model outputs. Its SHA-256 is
`155187801d83e4ee8247512732bdf525ef50abb60d21bccf9c362cd20128913c`.
Inputs are the existing A13 11 cash-labelled frames and one additional ID-positive
frame. There are 7 cash positives, 4 cash negatives and 2 ID labels. Other class labels
are excluded. Filenames, expected answers and organizer outcomes never enter prompts.

| Variant | Input per call | Calls |
| --- | --- | ---: |
| `full` | One native-source full frame | 12 |
| `tiles384` | One fixed 384 px source tile; 6 overlapping tiles cover each frame | 72 |
| `tiles384_temporal3` | Same tile at target minus 0.4 s, target, target plus 0.4 s | 72 |

Temporal input is exactly three chronological images. The model is asked only about
the second image. Context does not create a positive when an object is visible only
in a neighboring image. No missing context is replaced, repeated or clamped. Failed
decodes are unknown. All crops come directly from the native source, using the frozen
general geometry, before the Qwen processor rounds dimensions to its patch grid.

Each call predicts only `cash` and `id_card`: `yes`, `no` or `unknown`. Invalid JSON,
duplicate keys, booleans, missing keys and extra keys are invalid responses. A frame
union is yes if any tile explicitly says yes, no only if all tiles explicitly say no,
and unknown otherwise. A frame's label is scored once against that union, never
against each tile. No object boxes, owners, order of actions or rule decisions are made.

The model loading and template/generate/decode path reuse the working local pattern in
`~/datathon26-annotation-preview/realtime/descriptions.py`, adapted to image lists to
preserve exactly three inputs. Settings: offline local weights, bfloat16, SDPA, greedy
generation, 32 new tokens, at most 5 seconds per generation, a 600-second inference
budget after loading. The argv also has a 650-second hard process limit after acquiring
the GPU flock. Missing/budget-expired calls remain unknown. Task order covers all full
frames, then alternates spatial/temporal tile rounds across all inputs, including clean
negatives. The budget can end with a partial result; no result is filled in.

Execute the ready datathon2 argv outside the worker sandbox:

```bash
.venv/bin/python -c 'import json, subprocess; from pathlib import Path; cmd=json.loads(Path("attempts/A21-deadline/recognition/qwen-gpu-command.json").read_text()); raise SystemExit(subprocess.run(cmd).returncode)'
```

It uses `/home/ubuntu/dt26-validation/.venv/bin/python`, the existing
`/home/ubuntu/dt26-validation/models/Qwen3-VL-4B-Instruct`, and original videos under
`/home/ubuntu/data/open/videos`. It acquires `~/.cache/datathon-workers/gpu.lock`.
For the datathon3 transferred copy, change only argv model/video/interpreter paths as
appropriate; keep the manifest unchanged. Keep the scripts inside the repository so
their existing geometry, decoder and counter imports resolve. No downloads are needed.

Outputs are text/numeric only: `qwen-results/metadata.json`, `results.json` and
`summary.json`. Every class/variant has TP, FP, FN, TN and unknown counts; invalid
responses and unrun calls are counted separately. Per-call artifacts record actual
source/decoded timestamps, source boxes, image patch grids, token counts and latency.
Model identity includes the config hash and weight filenames/sizes; the downloaded
folder does not record a Git revision, so no revision is invented.

Validation actually run:

- Real CPU preflight in the requested Qwen environment: all 12 inputs, all 36 temporal
  source frames, and real processor calls on single full and triple tile images passed.
  The full-frame grid was `[1,52,28]` with 458 input tokens; three tile grids were
  `[1,24,24]` each, with 576 input tokens. See `qwen-preflight/preflight.json`.
- Environment: Transformers 5.20.1, torch 2.11.0+cu128. Only CPU preprocessing was run.
- `RULE_SCOPE=detector .venv/bin/pytest -q attempts/A21-deadline/recognition/test_qwen_compare.py tests/test_object_refinement.py tests/test_no_label_access.py`:
  62 passed in 5.36 s, including parser/union/unknown/budget/failure checks and the
  existing cutoff and mapping tests. Mocked failures are not inference measurements.
- Ruff check/format and `git diff --check` passed. No current test failures.

Changes are confined to recognition scripts, tests and diagnostic artifacts. The
existing OWLv2 summary helper now accepts optional classes/variants, so Qwen reuses the
same tested counter; existing callers retain their defaults. No dependencies or
production modules were changed for this continuation.

Skipped: Qwen CUDA execution, further variants and production promotion. Risk: only two
ID labels and no localization gold; three-frame context does not prove non-presentation
or adequate interval visibility. The ten-minute budget may leave unknowns.
