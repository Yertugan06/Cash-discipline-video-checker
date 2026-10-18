GPU_RUN_READY. Local-only temporal laptop-state pilot; production is unchanged.

Changed only `attempts/A22-recovery/laptop-probe/`: runner, frozen manifest, exact CPU/GPU argv, CPU selection evidence, this report and readiness marker. Existing recognition/tracking and older dirty files are preserved. Base imports come from `shared/a22/base`, the requested combined main5fae source; per-file hashes are in `cpu-selection/metadata.json`.

The manifest freezes generic confirmed cashier EXIT selection and the short state prompt before any model outputs. Each EXIT retains its own actor ID and sequence; no TRACK_LOST/workstation-away/cutoff substitute. The base builder emits confirmed departures as EXIT without a confirmed_exit field, so the runner follows Context.room_exits: accept the EXIT type unless explicitly false. Initial CPU preparation incorrectly required the optional field and yielded zero windows; that runner filter was corrected before the measured preparation below. No backend code changed.

Actual CPU preparation: 8 inputs, 9 EXIT windows, 37 native crops, 4.176 seconds including the self-check. No model inference ran.

| Evaluation input | Selection result | Base EXIT times (seconds) | Crops |
|---|---|---|---|
| X11 | triggered | 11.5, 17.0, 20.5 | 13 |
| X12 | triggered | 37.5 | 4 |
| X28 | triggered | 14.0 | 4 |
| X29 | triggered | 13.5 | 4 |
| X22 | triggered | 17.5, 19.5 | 8 |
| X23 | triggered | 14.5 | 4 |
| X20 | no_trigger | — | 0 |
| X21 | no_trigger | — | 0 |

X20/X21 remain no-trigger. The builder emits multiple windows for X11 and X22; these are logged separately rather than choosing by expected outcome. EXIT quality remains an upstream limitation, not new ground truth. No organizer time, filename, expected state or verdict is supplied to the model. Index IDs only choose the requested input files and their source SHA.

The generic global luminance test detected one X11 drop: mean gray 138.201 to 19.581 between cache samples 15.5 and 16.0 seconds. It added the real sample at 15.5. This reports a CV sampling change only, not laptop power or lock state. The rest of the tested windows had no qualifying drop in their frozen four-second lookback. Crops retain calibrated native-source pixels with the existing 25% margin. Native crop sizes range 100–120 pixels wide and 101–127 high. Qwen's processor may resize these to its frozen pixel budget; that supplies no new detail. Actual decoded times are logged separately from cache targets (maximum permitted difference 0.12 seconds).

Output is one directly visible state per crop: working, locked, closed or unknown, with actual decoded timestamps. Transitions only connect adjacent known, changed state answers; no propagation across unknowns. Invalid model JSON maps the entire sequence to unknown_error/unknown and retains raw text for diagnosis. No rule verdict, legal inference, subjective confidence or production hook exists. Model-load/CUDA failures fail the command explicitly, rather than yielding negative visual evidence.

Actually run: the small selection/strict-parser assertions (positive/unknown and invalid enum, extra field, duplicate key, wrong count) passed; actual eight-input CPU event/crop preparation passed; Ruff check and format check passed; scoped git diff --check passed. No broad suite or GPU call was run. Metadata records source/video/cache/policy/runner SHA256 plus decoded RGB/crop SHA256 and native dimensions without exposing pixels. GPU metadata will use the existing model identity helper (small-file content hashes plus shard size/mtime fingerprint, not a full weight-byte digest), local revision if available, torch/transformers versions, processor grids, model-load and per-case/per-window inference time.

Datathon3 execution: copy this directory to `~/workspaces/datathon26-workers/shared/a22/laptop-probe/`, activate its prepared Qwen-capable Python environment, then execute the argv array in `gpu-command.json`. `python` resolves in that environment; the worker cannot verify datathon3's interpreter from this sandbox. The model path is an explicit argument pointing to `shared/a22/models/Qwen3-VL-8B-Instruct`; all loads are offline. An existing GPU-lock directory is required. `flock --nonblock` rejects an already-busy GPU, and timeout bounds the whole job to 600 seconds. The generation budget is 480 seconds, 35 seconds/request, 96 new tokens/sequence. Run only once the parent finishes transferring weights. The GPU run independently records its exact CPU selection before loading the model.

Pending: parent actual CUDA run and state comparison. No measured visual-state improvement or production promotion is claimed. All40 influenced development; this is a small development pilot, not held-out accuracy.
