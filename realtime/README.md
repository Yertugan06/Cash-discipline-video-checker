# realtime/ - live verdict gateway

A separate process in front of the checker API. The checker (`backend/`) is unchanged.
The gateway pushes each job's status and final verdict to the browser over a WebSocket
as soon as it changes.

```
browser --ws /ws, POST /api/upload, POST /api/run-folder--> gateway :8100 --X-API-Key--> checker :8000
```

- Videos (browser uploads or every `.mov` in `VIDEO_DIR`) go into one FIFO. The gateway
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
  `STATE_FILE`). They are team ground truth: they stay in the gateway and never reach the checker.
- To keep a finished run for `/compare`, copy `state.json` to `state.<name>.json` in the same
  folder before starting the next run.
- The page loads `/api/state` over plain HTTP on open, then follows `/ws`. While the socket
  is down it re-reads `/api/state` every 3 s.

## Endpoints

| Method | Path | What |
|---|---|---|
| GET | `/` | the live page (`static/index.html`) |
| WS | `/ws` | `{"type":"snapshot","items":[...]}` on connect, then `{"type":"item","item":{...}}` per change |
| POST | `/api/upload` | multipart, field `files` (one or more `.mov`) |
| POST | `/api/run-folder` | queues every `.mov` in `VIDEO_DIR`, in clip-number order |
| GET | `/api/state` | same as the snapshot |
| GET | `/api/config` | `{folder, labels}` |
| GET | `/api/items/{id}/video` | the item's source video (Range requests, for the replay player) |
| GET | `/api/items/{id}/trace` | the checker's per-job trace (boxes, roles, events), proxied with the gateway's key |
| GET | `/compare` | page comparing runs per clip; the `live` column follows `/ws` |
| GET | `/api/runs` | `{"runs": ["live", ...saved]}`; saved runs are files `state.<name>.json` next to `STATE_FILE` |
| GET | `/api/runs/{name}` | that run's items without evidence images |
| GET | `/annotate` | page for writing what really happens in each clip (blind: no system output until a clip is marked done) |
| GET | `/api/clips`, `/api/clips/{key}/video` | clips in `VIDEO_DIR` with annotation status; a clip's video |
| GET, PUT | `/api/annotations/{key}?base_version=` | a clip's timeline (`realtime/annotations.py` schema); PUT refuses with 409 if someone saved since `base_version` |
| GET | `/api/annotations-score?run=&clip=` | done timelines vs that run's traces: recall/extra per action, role accuracy, clips with no trace |

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

Tests: `tests/test_realtime_gateway.py` (fake checker via `httpx.MockTransport`).
