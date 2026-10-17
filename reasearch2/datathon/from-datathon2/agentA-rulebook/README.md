# ForteBank cash-discipline video checker — v1

A fully local video pipeline: scene grounding, person detection and ByteTrack,
position/behaviour roles, RTMPose hand points, object detection, crop states,
events, client sessions, cash provenance, and 16 priority-1 rules. Results contain
Russian/English descriptions, codex citations and 1–3 annotated JPEG frames.

**This is an experimental detector, not a production bank control.** The first
CPU validation found substantial misses and false alarms. See LIMITATIONS.md.
The CUDA image and all four model adapters have passed offline checks on a Brev
NVIDIA L4. The first real clip completed, but its labelled rule was missed. The
full 42-file evaluation is running on the VM; its final scores and the worst-case
five-minute target are not established yet. Results come from real local models.

## Current cloud workspace

Following the later request to move work off the laptop, the service, weights and
the explicitly approved hackathon dataset are on Brev instance `datathon` at
`~/forte-cash-checker`. Builds, model inference and evaluation run there. The
original local deployment remains available below for a jury that requires it.

- App: <http://localhost:8018>
- Live HTML results/logs: <http://localhost:8019>
- First real clip report: <http://localhost:8019/first-video/index.html>
- Full evaluation report when finished: <http://localhost:8019/gpu/index.html>

These links use an SSH tunnel and are not public endpoints. Enter `API_KEY` from
the private ignored `.env.brev` file in the app. The VM's original key is in
`~/forte-cash-checker/.env`; neither file belongs in Git or the frontend bundle.

Reconnect both ports through the Brev-managed gateway alias if the tunnel closes:

```sh
brev refresh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8018:127.0.0.1:8000 \
  -L 127.0.0.1:8019:127.0.0.1:8081 datathon
```

On the VM, inspect the app and the detached evaluation:

```sh
cd ~/forte-cash-checker
docker compose -p forte-cloud -f compose.yaml -f compose.gpu.yaml -f compose.cloud.yaml logs --tail 100 checker
docker logs --tail 100 forte-full-eval-20261017
```

App artifacts are in `runtime/`, evaluation artifacts in `eval_runtime/`, and model
checks/logs in `output/`. The viewer polls evaluation progress and shows each
finished clip's labels, predictions and runtime while the batch continues. The
batch container has networking disabled and does not depend on the laptop tunnel.

The viewer listens on VM loopback port 8081. To restart it after a VM reboot:

```sh
cd ~/forte-cash-checker
cp scripts/model_results.html output/index.html
python3 scripts/serve_model_results.py --directory output --port 8081 --hardware 'Brev datathon / NVIDIA L4'
```

`compose.cloud.yaml` mounts the backend/scripts from the VM checkout for development.
Its `runtime/` directory is owned by the image's worker, UID 10001. Keep the image's
worker account when running model containers; an arbitrary numeric UID without a
username causes Torch imports to fail.

## Start on the NVIDIA PC

Use Linux with NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), or [Docker Desktop with WSL2 GPU support](https://docs.docker.com/desktop/features/gpu/). An internet connection is needed for the initial image build and
public weight downloads. Processing then works offline. No cloud AI account is needed.

```sh
# Run once; retain an existing .env instead of overwriting its key.
python3 -c 'import secrets; print("API_KEY=" + secrets.token_urlsafe(32))' > .env
chmod 600 .env
sh scripts/download_weights.sh
# Start/rebuild with CUDA 12.8 PyTorch and GPU access:
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```

On Windows, use `python scripts/download_weights.py` for the download step, then
run the Compose command from the project folder. Downloads are approximately 1.4 GB;
allow additional space for the image and runtime artifacts. Copy the `weights/`
folder to the target PC if it will have no internet. Do not copy `.venv/` or
`node_modules/` between operating systems.

Open <http://localhost:8000>. The **API key is a local service password**, required
by the jury API contract. Enter the value after `API_KEY=` in your private `.env`.
It stays in page memory and is not embedded in the UI bundle or browser storage.
For a different port, prefix the command with `API_PORT=8018` or add it to `.env`.

For CPU use, run `docker compose up --build`. The default CPU image also works
with `docker compose up` after its initial build. The CUDA preset sets `DEVICE=cuda`;
it fails explicitly if CUDA is unavailable rather than silently using CPU for the
Torch detectors. RTMPose uses CPU ONNX Runtime by default; a CUDA ONNX provider is
used if separately installed and available. GPU performance is unverified here.

The service uses one worker. SQLite, uploads, results and perception caches reside
in the local `work` volume. Weights, configuration and optional training data are
mounted read-only. `docker compose down` retains results; `down -v` removes them.
The API is published only on loopback. For jury/LAN access, explicitly change the
host address in the Compose port mapping and retain API-key authentication.

## API

Both endpoints require `X-API-Key`; wrong/missing keys return 401.

```sh
curl -X POST http://localhost:8000/api/v1/analyze \
  -H 'X-API-Key: <key>' -F 'file=@video.mov'
curl http://localhost:8000/api/v1/jobs/<job_id> -H 'X-API-Key: <key>'
```

POST returns HTTP 202 with `{"job_id":"..."}` after saving the upload. GET returns
`processing`, `done` or `failed`. Done results preserve the jury contract and add
`rule_id`, `source`, `source_url`, `strength`, confidence, English text, event log,
coverage warnings and `perception_cached`. The verdict is derived from actual rule
findings. Errors fail the job; missing weights never produce a clean verdict.
Limits: non-empty `.mov`, 64 MiB, 180 s, and 4096×4096 pixels. The processing timeout
is 300 s. The full HTTP deadline also includes upload and queue time.

`POST /api/v1/analyze?debug=true` additionally renders a debug MP4 with zones,
boxes, track IDs, roles, hands and states. Fetch it with the same key at
`GET /api/v1/jobs/{job_id}/debug`. The UI uses the two jury endpoints.

## Evaluate the training clips

Keep private inputs here; they are excluded from Git and image builds:

```text
data/videos/*.mov
data/open_labels.xlsx
data/Cash_Discipline_Cases_Rules.xlsx
```

Run directly with an installed local Python environment:

```sh
python eval.py --videos data/videos --labels data/open_labels.xlsx --out reports/gpu --device cuda --debug
python eval.py --videos data/videos --labels data/open_labels.xlsx --out reports/http --via-api --debug
```

Or use the running GPU container, without installing Python dependencies on the host:

```sh
docker compose -f compose.yaml -f compose.gpu.yaml exec checker python eval.py \
  --videos data/videos --labels data/open_labels.xlsx --out runtime/reports/gpu --device cuda --debug
docker compose -f compose.yaml -f compose.gpu.yaml cp checker:/app/runtime/reports/gpu ./reports/gpu
```

Reports include `summary.csv`, `per_video.csv`, `per_rule.csv`, `index.html`,
`results.json`, `summary.json`, `misses.json`, `incremental_rules.csv` and matching
primary-case `pairs.csv` when available. The HTML shows labels, predictions,
annotated evidence, event timelines and debug videos. It contains private footage
and must remain local. Detailed model observations are saved as `perception.json`
inside direct-run artifacts for local diagnosis.

SHA-256 merges X-4/X-47 (57 s and 68 s) and X-5/X-48. Each of the 40 unique videos
runs once. `all_unique` scores unique files; `all_clips` weights merged results by
their 42 aliases, including repeated event weights. Time matching is maximum
one-to-one within inclusive ±1/2/5 s. Per-rule scores use primary case links at ±2 s;
these are incomplete labels, so unmatched findings are label-relative false alarms.

The held-out layout is `Desk near the door` (9 clips); the other 31 unique files
are `training`. Duplicate groups stay in one split. Change it with
`--held-out-layout`. Threshold tuning must use training pairs only, followed by a
frozen held-out run. The current split is a diagnostic breakdown, not a validated
generalisation claim. `incremental_rules.csv` re-scores independent rule additions
without repeating the expensive perception pass.

`--fps` changes direct sampling (default 5). For HTTP evaluation configure the
server's `SAMPLE_FPS`. CPU experiments at low fps cannot establish 5-fps accuracy.
`--reuse-perception` explicitly replays compatible local model observations for
rule tuning; cached timings are not uncached inference benchmarks. The cache key
includes video SHA-256, model revisions, sampling rate, prompts and configuration.
`--via-api` reads `API_KEY` from the environment and accepts only loopback origins;
proxy settings are ignored. Failures remain in the denominator and cause exit 1.

## Calibration and detector configuration

`config/perception.yaml` contains prompts, detector sizes, score thresholds,
classification margins and smoothing settings. No rule depends on a clip name or
fixed camera coordinates. Static zones are derived from the first approximately
two seconds. Cashier/client sides use the desk and laptop; uncertain calibration
is reported and dependent checks are limited.

For a difficult view, get the SHA-256 with `sha256sum path/to/video.mov` (or a local
hash tool), then edit `config/overrides.yaml`. Keys must be complete hashes.
Example structure; coordinates are normalised to the frame, not pixel positions:

```yaml
videos:
  '<full video sha256>':
    objects:
      desk: [0.15, 0.25, 0.85, 0.80]
      laptop: [0.20, 0.35, 0.40, 0.55]
    zones:
      cashier: [[0, 0], [0.4, 0], [0.4, 1], [0, 1]]
      client: [[0.6, 0], [1, 0], [1, 1], [0.6, 1]]
```

The numbers above are illustrative, not presets for any supplied video. Add safe,
door and counter object boxes as needed. Reload configuration with a new job.
Roles use posture, position and bag behaviour; there is no face recognition or
identity matching. Head position supports only the food/cup cue.

`LocalModels.objects` in `backend/perception.py` is the detector replacement hook:
return normalised `Detection` objects for the configured labels. The default uses
OWLv2 on full frames plus a desk crop for small cash/documents. No language model
generates a verdict or legal interpretation.

Regenerate the codex and documentation after editing the workbooks/templates:

```sh
python scripts/convert_codex.py
python scripts/export_contract.py
```

All rule text, minimum-duration proposals, report templates and legal references
are loaded from `codex.yaml`. Priority-2 rules and the three explicitly excluded
rules remain known misses. See RULES.md and MODELS.md for exact coverage/licences.

## Local development and checks

Exercise every production model adapter using synthetic pixels, without uploading
footage. The check prints progress for each pass and writes `run.log` and
`result.json` with model revisions, devices, timings and peak Torch GPU memory:

```sh
python scripts/check_models.py --device cuda --out reports/model-check
# For the CUDA service container:
docker compose -f compose.yaml -f compose.gpu.yaml exec checker python scripts/check_models.py --device cuda --out /app/runtime/reports/model-check
```

This checks execution, not detection accuracy or the full-video deadline. RTMPose
reports its own execution device separately from the Torch models.

Requires Python 3.12+, Node 22.12+, ffmpeg and ffprobe. For CPU development:

```sh
python3 -m venv .venv
.venv/bin/pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements-dev.txt
cd frontend
npm ci
npm test
npm run build
cd ..
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend scripts tests eval.py
```

Export `API_KEY` from `.env`, then run
`.venv/bin/uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000`.
Use one Uvicorn worker. After any model change, validate the actual checkpoint
licence and regenerate the pinned manifest before distributing it.
