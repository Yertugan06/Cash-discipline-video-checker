# realtime/ - live verdict gateway

A separate process in front of the checker API. It submits videos through the existing
checker contract and keeps annotations outside inference.
The gateway pushes each job's status and final verdict to the browser over a WebSocket
as soon as it changes.

```
browser --ws /ws, POST /api/upload, POST /api/run-folder--> gateway :8100 --X-API-Key--> checker :8000
```

- Videos (browser uploads or every `.mov`/`.mp4`/`.mkv` in `VIDEO_DIR`) go into one FIFO. The gateway
  submits them **one at a time**. The checker's per-job budget (270 s) starts at upload
  time, so submitting 40 at once would time out the tail of the queue.
- The checker's `API_KEY` stays in the gateway; the browser never sees it.
- `LABELS` (optional, `data/prepared/videos.jsonl`) puts the organizer verdict next to each
  result and counts matches, false alarms and misses. Labels never reach the checker.
- With `STATE_FILE` set, every change is written to that JSON file. A viewer who connects
  later gets every past result in the first snapshot. A restarted gateway reloads it,
  re-queues unfinished folder clips from scratch, and marks unfinished uploads as failed
  (their temp files are gone).
- Annotations are saved as `annotations/<clip key>.json` next to `STATE_FILE` (so annotating needs
  `STATE_FILE`). Reviewed annotations are reference material; unreviewed AI drafts remain marked
  as drafts. Both stay in the gateway and never reach the checker.
- `/annotate` defaults to **Description**: watch the video beside one editable whole-clip
  description, correct the local model's draft, then **Looks right · next clip**. No start/end
  times or per-second labels are required. Existing timeline notes are combined in action order
  without deleting the original rows. Edits autosave; a draft arriving later never replaces
  text the person has started writing. `N` pauses and focuses the description; Ctrl/Cmd+Enter
  saves it as reviewed and opens the next clip. Share links with `?view=easy`.
- **Detailed review** (`?view=detailed`) retains the editable event timeline, range selection,
  quick presets, and detector review. `I` / `O` mark the range start/end; `N` focuses a note,
  Ctrl/Cmd+Enter adds it. Search clips and filter unfinished ones in the library. Camera layout
  and people count are under **Clip details**. Both views preserve the same saved annotation.
- The optional `python -m realtime.descriptions --videos VIDEO_DIR --output STATE_DIR/descriptions
  --model /local/Qwen3-VL-4B-Instruct --first X-2` worker runs entirely on the GPU VM, using
  existing PyAV, torch, transformers, and Pydantic dependencies. It samples up to 64 frames over
  the whole video using presentation times, generates neutral action descriptions, and records
  model, source hash, sampled times, and errors. It resumes completed drafts and reuses identical
  videos. No labels, rules, manual annotations, or cloud model APIs are used by the worker.
  Draft files are separate from human corrections; loading one sets `description_source=ai_draft`,
  `description_model`, `assisted=true`, and draft status. Only the reviewer marks a clip done.
  Descriptions can miss brief actions or misidentify small objects and must be checked.
- **Review suggestions** loads saved events and per-frame object boxes from the selected run.
  Confirm an event to add it to the timeline, correct its time or fields, or reject it with a
  comment. Confirming an exactly matching existing event keeps the manual note. Object feedback
  is saved separately: confirming a box records a sighting, never a made-up placement action.
  **Detect this clip** queues only the current clip through the existing local checker; no new
  model or cloud processing is involved. Missing/expired traces are reported explicitly.
- Detailed review starts without model output. Loading suggestions permanently marks that
  clip `assisted`; accepted/corrected event rows retain their suggestion IDs, and `reviews`
  stores decisions, source run, original labels/boxes, corrections, and comments. Older annotation
  JSON files load with defaults. **Needs a closer look** notes stay saved but are excluded from
  confirmed event scoring. Score summaries show how many timelines used suggestions.
- Autosaves are serialized and preserve edits made while a request is pending. A failed save
  can be retried; version conflicts stop navigation and offer **Download my notes**. Add or clear
  an unfinished composer note before switching clips. **Save now** also adds the current note
  after validation; unfinished notes are explicitly labeled as unsaved. **Save & mark done**
  finishes a clip.
- To keep a finished run for `/compare`, copy `state.json` to `state.<name>.json` in the same
  folder before starting the next run.
- The page loads `/api/state` over plain HTTP on open, then follows `/ws`. While the socket
  is down it re-reads `/api/state` every 3 s.
- With `STATE_FILE` configured, uploaded replay videos persist in its sibling `uploads/`
  directory across gateway restarts. Remove old uploads explicitly when no saved run needs them.
- On the live page, choose a saved run in **Run / Attempt**, or use **Previous / Next**
  (left/right arrow keys outside form fields and the video player). Previous from Live opens
  the most recently saved snapshot. **Back to Live** returns to the current feed; live updates
  keep arriving while you browse history. **Refresh runs** discovers newly saved snapshots.
  The selected run is stored in the URL (`/?run=<name>`), so reload and browser Back/Forward work.
- Saved results include their evidence and replay video when available. Offline replay snapshots
  can omit evidence images and checker job IDs; their verdicts and source video still open, with
  an explicit message when no trace was recorded. A saved state does not preserve checker traces
  or uploaded video files after those files have been removed.

## Endpoints

| Method | Path | What |
|---|---|---|
| GET | `/` | the live page (`static/index.html`) |
| WS | `/ws` | `{"type":"snapshot","items":[...]}` on connect, then `{"type":"item","item":{...}}` per change |
| POST | `/api/upload` | multipart, field `files` (one or more `.mov`/`.mp4`/`.mkv`) |
| POST | `/api/run-folder` | queues every `.mov`/`.mp4`/`.mkv` in `VIDEO_DIR`, in clip-number order |
| GET | `/api/state` | same as the snapshot |
| GET | `/api/config` | `{folder, labels}` |
| GET | `/api/items/{id}/video?run=live` | the selected run's source video (Range requests); `run` defaults to `live` |
| GET | `/api/items/{id}/trace?run=live` | the selected run's checker trace (boxes, roles, events), proxied with the gateway's key; `run` defaults to `live` |
| GET | `/compare` | page comparing runs per clip; the `live` column follows `/ws` |
| GET | `/evaluation` | published verdict/observation audit; clip links open annotation |
| GET | `/api/evaluation` | fixed `evaluation.json` beside `STATE_FILE`; explicit 404 until published |
| GET | `/api/runs` | `{"runs": ["live", ...saved]}`; saved runs are files `state.<name>.json` next to `STATE_FILE` |
| GET | `/api/runs/{name}` | compact items for comparison; `?full=true` returns original items including evidence |
| GET | `/annotate` | video, range selection, editable timeline, and optional detector review |
| GET | `/annotate/assets/{name}` | annotation JavaScript/CSS; only the two known asset names are accepted |
| GET | `/api/clips`, `/api/clips/{key}/video` | clips in `VIDEO_DIR` with annotation status; a clip's video |
| POST | `/api/clips/{key}/analyze` | queue just this clip on the local detector; returns `item_id`, reuses a pending job |
| GET, PUT | `/api/annotations/{key}?base_version=` | a clip's timeline (`realtime/annotations.py` schema); PUT refuses with 409 if someone saved since `base_version` |
| GET | `/api/annotation-description/{key}` | local video description draft and provenance; explicit unavailable/queued/processing/ready/failed status |
| GET | `/api/annotation-suggestions/{key}?run=live` | saved event suggestions and object boxes with stable IDs for review; 404 when no result/trace exists |
| GET | `/api/annotations-score?run=&clip=` | done timelines vs traces; description-only clips are listed separately and excluded from timed event scoring |

Item `status`: `queued -> submitting -> processing -> done | failed`. A `done` item carries
the checker's `DoneJob` verbatim in `result`.

## Run

```
CHECKER_URL=http://127.0.0.1:8000 API_KEY=... VIDEO_DIR=~/data/open/videos \
LABELS=data/prepared/videos.jsonl STATE_FILE=runtime/realtime-state.json \
python -m uvicorn --factory realtime.gateway:create_app --host 127.0.0.1 --port 8100
```

uvicorn needs a WebSocket library (`websockets`, see `requirements.txt`) that the checker
image does not have; without it every `/ws` upgrade gets a 404. On `datathon` the gateway
runs from `realtime/Dockerfile` (checker image + `websockets`):

```
mkdir -p /tmp/rt-ctx && cp -r realtime /tmp/rt-ctx/
docker build -f /tmp/rt-ctx/realtime/Dockerfile --build-arg BASE=forte-cash-checker:cuda \
  -t datathon26-realtime /tmp/rt-ctx
mkdir -p ~/realtime-state && sudo chown 10001:10001 ~/realtime-state   # image user `checker`
docker run -d --name datathon26-realtime --restart unless-stopped --network host \
  --env-file ~/datathon26/.env \
  -e VIDEO_DIR=/videos -e LABELS=/labels/videos.jsonl -e STATE_FILE=/state/state.json \
  -v $HOME/data/open/videos:/videos:ro \
  -v $HOME/datathon26/data/prepared/videos.jsonl:/labels/videos.jsonl:ro \
  -v $HOME/realtime-state:/state datathon26-realtime
```

Open it from your machine through a tunnel: `ssh -N -L 8100:127.0.0.1:8100 datathon`,
then go to http://localhost:8100.

## Current one-VM review service

A21 runs on **datathon2** in `~/workspaces/datathon26-workers/shared/a21/candidate`.
Checker **8003**, gateway **8103**, all model weights and Python environments are
on that VM. The former 8002/8102 preview is stopped; its data remains backed up.
All 42 annotation records and 42 local description drafts were retained.

Open a tunnel, then use <http://localhost:8103/evaluation>, `/annotate`, or `/compare`:

```bash
ssh -NT -o ServerAliveInterval=30 -L 8103:127.0.0.1:8103 datathon2
```

The running service was started with this launcher (refuses to replace busy ports):

```bash
python3 ~/workspaces/datathon26-workers/shared/a21/boot_candidate.py \
  --root ~/workspaces/datathon26-workers/shared/a21/candidate \
  --checker-python ~/workspaces/datathon26-workers/worker-1/.venv/bin/python \
  --gateway-python ~/datathon26-annotation-preview/.venv/bin/python \
  --model-python ~/dt26-validation/.venv/bin/python \
  --weights ~/agentA-rulebook/weights \
  --model ~/dt26-validation/models/Qwen3-VL-4B-Instruct \
  --videos ~/data/open/videos --visual-checks
```

For a new checkout, use `attempts/A21-deadline/boot_candidate.py` and substitute local
paths. The launcher defaults to VLM **on** at the user's request; `--no-visual-checks`
disables it. Generic `Settings.from_env()` remains opt-in via `F1_VISUAL_CHECKS=1`.
This helper uses `RULE_SCOPE=detector` and creates a private mode-0600 service key.
The separate model environment needs the measured Transformers 5.20.1 / Accelerate 1.15.0
stack; the F1 environment is unchanged. No cloud inference or second VM is required.

`runtime/realtime/state.live.json` holds the current run; `state.*.json` holds earlier
comparisons. `annotations/`, `descriptions/` and the published `evaluation.json` share
that directory. Raw results/images and checker traces remain on the VM. A Git checkout
alone does not restore runtime data or model weights. Never overwrite this directory
with an empty deployment snapshot.

The complete enabled API run is 30/40 unique verdicts, 0/19 clean false alarms and
42/42 successful jobs; the VLM added no correct detections. See
[the measured release report](../attempts/A21-deadline/RESULTS.md).

Tests (no GPU or checker service required):

```
python -m pytest tests/test_realtime_gateway.py tests/test_realtime_annotations.py -q
node --test --test-isolation=none tests/realtime_frontend.test.mjs
node --test --test-isolation=none tests/annotation_frontend.test.mjs
```

Gateway tests use a fake checker via `httpx.MockTransport`. Frontend tests exercise run switching,
out-of-order responses, saved-run links, offline results, and live updates while browsing history.
Annotation tests also cover old-file compatibility, review provenance, object feedback, invalid
inputs, one-clip detection, concurrent browser edits during saving, retry/conflict handling,
and navigation with unfinished notes.

## Attempt metadata

Saved item arrays remain `state.<run>.json`. Add an optional adjacent
`state.<run>.meta.json` with real provenance:

```json
{"attempt_prefix":"A23","title":"Synthetic videos","source_commit":"4a3b9ea"}
```

Use `state.live.meta.json` for the active feed, regardless of the `STATE_FILE` name.
Copy its metadata when archiving a live run. A run ID starting with `a23-` can supply
its own prefix if no sidecar prefix exists; other legacy IDs stay **Legacy / unknown**.
No prefix is inferred from the running checkout. Metadata files are excluded from run
items. Invalid metadata produces an explicit error. Runs sort by numeric attempt,
retaining file order within one attempt; the live navigator keeps the current feed last.

`/api/runs` retains `runs: string[]` and adds `metadata: {runId: metadata}`.
`/api/runs/{name}`, `/api/state`, and WebSocket snapshots add `metadata` alongside
unchanged item payloads. Metadata includes `attempt_prefix` (string or null), `title`,
`source_commit` (string or null), and a generated `label`; extra sidecar keys survive.

The existing `evaluation.json` audit may additionally include top-level
`attempt_prefix`, `source_commit`, and `attempt_reports`, an array of:

```json
{"attempt_prefix":"A23","title":"Synthetic videos","source_commit":"4a3b9ea","status":"completed","kind":"synthetic","summary":"Actual result summary, including any unscored limits.","runs":["a23-synthetic"]}
```

Reports render as text and link to `/compare?run=<run>`. Older audit files still render.
Synthetic or other unlabelled runs show **Not scored**; publishing a report does not
invent organizer labels, accuracy scores, or future attempts.
