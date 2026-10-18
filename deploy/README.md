# Deployment

This covers WP1's part of the stack: the FastAPI app container, the reverse
proxy, and the systemd unit that keeps it running. vLLM's own serving setup
(`deploy/vllm/`) is WP2's; see that directory for the perception server.

## Current validated review deployment (A21)

A21 uses **one datathon2 VM** with checker 8003, gateway 8103 and local Qwen3-VL-4B
safe-state checks. [Start/tunnel instructions](../realtime/README.md#current-one-vm-review-service)
and [measured results](../attempts/A21-deadline/RESULTS.md) are authoritative for that release.
The former 8002/8102 preview is stopped. A Git push does not copy model weights, restore
annotations or replace the separately running public A20 endpoint on datathon.

The Compose/Caddy/systemd steps below describe deployment options; they are not a claim
that Caddy/systemd manage the A21 review processes. `DETECTOR=vlm` below is the older
alternative server, distinct from A21's `DETECTOR=f1` plus `F1_VISUAL_CHECKS=1` helper.

## Pieces

| File | Purpose |
|---|---|
| `Dockerfile` (repo root) | Builds the app image: frontend (Vite build) + Python backend, torch/opencv/etc. for the F1 fallback. |
| `compose.yaml` (repo root) | Default (CPU/F1) compose service. `network_mode: host` so the app can reach vLLM at `127.0.0.1:8010` (architecture.md §8). |
| `compose.gpu.yaml` | Overlay: CUDA build + `gpus: all`, for `DETECTOR=f1` with GPU-accelerated perception. |
| `compose.cloud.yaml` | Dev overlay: mounts source over the built image for fast iteration. |
| `deploy/Caddyfile` | TLS-terminating reverse proxy in front of the app (`127.0.0.1:8000` -> `:443`). |
| `deploy/forte-checker.service` | systemd unit so `docker compose up` for this project survives a host reboot. |
| `deploy/.env.example` | Placeholder env file; copy to `.env` at the repo root (mode 600), fill in real values, never commit it. |

## Bring-up

```sh
cp deploy/.env.example .env && chmod 600 .env   # edit API_KEY, DETECTOR, ...
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d
curl -sf http://127.0.0.1:8000/healthz
ss -ltnp | grep ':8000 '   # 127.0.0.1:8000, or 0.0.0.0:8000 with API_HOST=0.0.0.0 behind Brev's proxy
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
sudo cp deploy/forte-checker.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now forte-checker.service
```

For `DETECTOR=vlm`, bring up `deploy/vllm/vllm.service` first (WP2) and only
switch the app's `DETECTOR` once `curl 127.0.0.1:8010/v1/models` answers; see
`/readyz` below.

For `DETECTOR=f1` with a GPU:

```sh
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

## Public URL (architecture.md §8)

**Last recorded public A20 deployment (2026-10-18):** Brev's port exposure on `datathon`,
`https://forte-checker-wwi4jcrss.gobrev.dev` -> port 8000:

```sh
brev ports open datathon 8000 --protocol http --public --hostname forte-checker
# in ~/datathon26/.env:  API_HOST=0.0.0.0   (then: docker compose ... up -d)
```

Brev's proxy connects from outside the host, not over loopback: with the app on
`127.0.0.1:8000` every request except the proxy's own `/healthz` (body `OK`) is a
Cloudflare 503. `API_HOST=0.0.0.0` fixes it. The VM's public IP filters every port
(22, 80, 443, 8000, 8888 checked from outside), so the app is reachable only
through the proxy, and `/api/v1` still needs `X-API-Key`. `--public` only turns
off the Brev login in front of the URL. Fallback if the proxy fails: a Cloudflare
Quick Tunnel from the VM to `127.0.0.1:8000` (`cloudflared tunnel --url ...`; its
URL changes on every restart).

The options, in order of preference:

1. **Brev's own port exposure** (if the VM is a Brev instance) -- the
   platform can publish a port directly; no reverse proxy to run yourself.
2. **The VM's public IP, fronted by Caddy** (this directory): works with
   either a real hostname (automatic Let's Encrypt cert) or the bare IP
   (`tls internal`, self-signed -- the jury's `curl` needs `-k` or a CA this
   isn't; prefer a hostname if at all possible).
3. **A tunnel** (e.g. an SSH reverse tunnel or a tunnelling service), used
   only as transport to whichever of the above is already serving locally --
   never as a substitute for running the service in-VM. Confirm with the
   organizers if in doubt (task.md FAQ D.23: "Обязателен публичный URL").

Whichever option is used, `/healthz` and `/readyz` must answer from outside
the VM before handing the URL + API key to the jury, and the uptime probe
(any external monitor hitting `/healthz` every few minutes) should be set up
against that same public URL.

## Readiness and health

- `GET /healthz` -- process is up; no body-level checks, no secrets.
- `GET /readyz` -- `DETECTOR=vlm`: `backend.vlm.client.check_ready` against
  vLLM's `/v1/models`; `DETECTOR=f1`: model weights present and match
  `models.lock.json` (`backend.f1.detector.models_loadable`), without
  loading torch. 503 when not ready, 200 when ready.

## Locality (architecture.md §8, task.md §7)

- vLLM binds to `127.0.0.1:8010` only (`deploy/vllm/serve.sh`); the app
  reaches it over loopback via `network_mode: host`, never a public address.
- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`
  are set in the Dockerfile; vLLM's own offline env vars are in its unit.
- Uploads and sampled frames are deleted when a job ends; results (with
  evidence JPEGs) are purged after `RESULTS_TTL_HOURS` (`backend/worker.py`,
  `backend/store.py`). Nothing is uploaded anywhere outside the VM while
  processing a video.
