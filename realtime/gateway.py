"""Realtime verdict gateway: a separate process in front of the checker API.

It keeps the checker untouched. Videos (browser uploads or a server-side
folder) go into one FIFO; the runner submits them to the checker one at a
time, because the checker's per-job budget starts at upload time, and polls
each job. Every state change is pushed to all connected WebSocket clients.

The checker's API key stays in this process; the browser never sees it.
Organizer labels (`LABELS`, optional) are shown next to verdicts for
comparison only - they never reach the checker.

    CHECKER_URL=http://127.0.0.1:8000 API_KEY=... VIDEO_DIR=~/data/open/videos \
    LABELS=data/prepared/videos.jsonl STATE_FILE=runtime/realtime-state.json \
    python -m uvicorn --factory realtime.gateway:create_app --host 127.0.0.1 --port 8100
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.media import VIDEO_SUFFIXES
from realtime.annotations import (
    Annotation,
    AnnotationStore,
    Stored,
    VersionConflict,
    score_clip,
    summarize,
    trace_events,
    vocabulary,
)

logger = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parent / "static"
# The clips are H.264 in a QuickTime container; browsers play it as mp4.
MEDIA_TYPES = {".mov": "video/mp4", ".mp4": "video/mp4", ".mkv": "video/x-matroska"}
ItemStatus = Literal["queued", "submitting", "processing", "done", "failed"]


@dataclass(frozen=True)
class GatewaySettings:
    checker_url: str
    api_key: str
    video_dir: Path | None
    labels_path: Path | None
    state_file: Path | None = None
    poll_s: float = 1.0
    job_timeout_s: float = 400.0

    @classmethod
    def from_env(cls) -> GatewaySettings:
        api_key = os.environ.get("API_KEY", "")
        if not api_key:
            raise RuntimeError("Set API_KEY to the checker's API key")
        video_dir = os.environ.get("VIDEO_DIR")
        labels = os.environ.get("LABELS")
        state_file = os.environ.get("STATE_FILE")
        return cls(
            checker_url=os.environ.get("CHECKER_URL", "http://127.0.0.1:8000").rstrip("/"),
            api_key=api_key,
            video_dir=Path(video_dir).expanduser() if video_dir else None,
            labels_path=Path(labels).expanduser() if labels else None,
            state_file=Path(state_file).expanduser() if state_file else None,
            poll_s=float(os.environ.get("POLL_S", "1.0")),
            job_timeout_s=float(os.environ.get("JOB_TIMEOUT_S", "400")),
        )


def video_suffix(name: str) -> str | None:
    """Lower-cased extension if `name` is a video the checker accepts, else None."""
    suffix = Path(name).suffix.lower()
    return suffix if suffix in VIDEO_SUFFIXES else None


def clip_key(name: str) -> str | None:
    """'Х-3.mov' (Cyrillic) / 'X-003' / 'x3' -> 'X-3'."""
    match = re.search(r"[XxХх]\s*-?\s*(\d+)", Path(name).stem)
    return f"X-{int(match.group(1))}" if match else None


def load_labels(path: Path | None) -> dict[str, str]:
    """clip key -> organizer verdict, from `data/prepared/videos.jsonl`."""
    if path is None:
        return {}
    labels: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = clip_key(row["original_id"])
        if key is None:
            raise ValueError(f"Unrecognised clip id in {path}: {row['original_id']!r}")
        labels[key] = row["organizer_verdict"]
    return labels


def compact(item: dict) -> dict:
    """An item without its evidence images, for comparing runs side by side."""
    result = item.get("result") or {}
    started, finished = item.get("started_at"), item.get("finished_at")
    return {
        "name": item["name"],
        "label": item.get("label"),
        "status": item["status"],
        "verdict": item.get("verdict"),
        "error": item.get("error"),
        "seconds": round(finished - started, 1) if started and finished else None,
        "violations": [
            {"rule_id": v.get("rule_id"), "type": v["type"], "timecode_sec": v["timecode_sec"]}
            for v in result.get("violations", [])
        ],
    }


class Item(BaseModel):
    id: str
    name: str
    source: Literal["upload", "folder"]
    status: ItemStatus = "queued"
    job_id: str | None = None
    verdict: str | None = None
    label: str | None = None
    error: str | None = None
    queued_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict | None = None  # the checker's DoneJob, verbatim


@dataclass
class Hub:
    """Item state plus the set of connected sockets; the single place items change.

    With a `state_file`, every change is written through to disk, so a late
    viewer and a restarted gateway both see every past result.
    """

    state_file: Path | None = None
    items: dict[str, Item] = field(default_factory=dict)
    sockets: set[WebSocket] = field(default_factory=set)
    # Publishes overlap (folder enqueue vs. the runner); one writer at a time, newest rows last.
    _save_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def load(self) -> list[Item]:
        if self.state_file is None or not self.state_file.exists():
            return []
        rows = json.loads(self.state_file.read_text(encoding="utf-8"))
        loaded = sorted((Item.model_validate(r) for r in rows), key=lambda i: i.queued_at)
        self.items = {i.id: i for i in loaded}
        return loaded

    def _save(self, rows: list[dict]) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_file)

    async def publish(self, item: Item) -> None:
        self.items[item.id] = item
        if self.state_file is not None:
            async with self._save_lock:
                rows = [i.model_dump() for i in self.items.values()]
                await asyncio.to_thread(self._save, rows)
        message = {"type": "item", "item": item.model_dump()}
        for socket in list(self.sockets):
            try:
                await socket.send_json(message)
            except Exception:
                self.sockets.discard(socket)

    def snapshot(self) -> dict:
        return {"type": "snapshot", "items": [i.model_dump() for i in self.items.values()]}


class Runner:
    def __init__(self, settings: GatewaySettings, hub: Hub, client: httpx.AsyncClient):
        self.settings = settings
        self.hub = hub
        self.client = client
        self.queue: asyncio.Queue[tuple[str, Path, bool]] = asyncio.Queue()

    async def enqueue(self, item: Item, path: Path, delete_after: bool) -> None:
        await self.hub.publish(item)
        await self.queue.put((item.id, path, delete_after))

    async def run_forever(self) -> None:
        while True:
            item_id, path, delete_after = await self.queue.get()
            try:
                await self._process(self.hub.items[item_id], path)
            except Exception as exc:
                logger.exception("Gateway item %s failed", item_id)
                await self.finish(self.hub.items[item_id], error=f"gateway error: {exc}")
            finally:
                if delete_after:
                    path.unlink(missing_ok=True)
                self.queue.task_done()

    async def _process(self, item: Item, path: Path) -> None:
        item = item.model_copy(update={"status": "submitting", "started_at": time.time()})
        await self.hub.publish(item)
        body = await asyncio.to_thread(path.read_bytes)
        response = await self.client.post(
            "/api/v1/analyze", files={"file": (item.name, body, MEDIA_TYPES[path.suffix.lower()])}
        )
        if response.status_code != 202:
            await self.finish(item, error=f"checker {response.status_code}: {response.text}")
            return
        item = item.model_copy(update={"status": "processing", "job_id": response.json()["job_id"]})
        await self.hub.publish(item)

        deadline = time.monotonic() + self.settings.job_timeout_s
        while time.monotonic() < deadline:
            await asyncio.sleep(self.settings.poll_s)
            poll = await self.client.get(f"/api/v1/jobs/{item.job_id}")
            if poll.status_code != 200:
                await self.finish(item, error=f"checker {poll.status_code}: {poll.text}")
                return
            job = poll.json()
            if job["status"] == "done":
                await self.finish(item, result=job)
                return
            if job["status"] == "failed":
                await self.finish(item, error=job["error"])
                return
        await self.finish(item, error=f"no result after {self.settings.job_timeout_s:.0f} s")

    async def finish(self, item: Item, *, result: dict | None = None, error: str | None = None):
        update = {"finished_at": time.time(), "error": error, "result": result}
        if result is not None:
            update |= {"status": "done", "verdict": result["verdict"]}
        else:
            update |= {"status": "failed"}
        await self.hub.publish(item.model_copy(update=update))


def create_app(
    settings: GatewaySettings | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """`transport` lets tests stand in a fake checker."""
    config = settings or GatewaySettings.from_env()
    labels = load_labels(config.labels_path)
    hub = Hub(state_file=config.state_file)
    upload_dir = Path(tempfile.mkdtemp(prefix="rt-gateway-"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            base_url=config.checker_url,
            headers={"X-API-Key": config.api_key},
            timeout=httpx.Timeout(60.0),
            transport=transport,
        ) as client:
            runner = Runner(config, hub, client)
            app.state.runner = runner
            await resume(runner, hub.load())
            task = asyncio.create_task(runner.run_forever())
            try:
                yield
            finally:
                task.cancel()

    async def resume(runner: Runner, loaded: list[Item]) -> None:
        """Items a previous gateway process left unfinished: folder clips go back
        in the queue from scratch; uploads are gone (temp files), so they fail."""
        for item in loaded:
            if item.status in ("done", "failed"):
                continue
            path = config.video_dir / item.name if config.video_dir else None
            if item.source == "folder" and path is not None and path.is_file():
                reset = {"status": "queued", "job_id": None, "started_at": None}
                await runner.enqueue(item.model_copy(update=reset), path, delete_after=False)
            else:
                await runner.finish(item, error="interrupted by a gateway restart")

    app = FastAPI(title="Realtime verdict gateway", lifespan=lifespan, docs_url=None)

    def new_item(name: str, source: Literal["upload", "folder"]) -> Item:
        key = clip_key(name)
        return Item(id=uuid4().hex, name=name, source=source, label=labels.get(key or ""))

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/compare")
    def compare_page() -> FileResponse:
        return FileResponse(STATIC / "compare.html")

    def saved_runs() -> dict[str, Path]:
        """Earlier runs are state files kept next to the live one: `state.<run name>.json`."""
        if config.state_file is None or not config.state_file.parent.is_dir():
            return {}
        files = sorted(
            config.state_file.parent.glob("state.*.json"), key=lambda p: p.stat().st_mtime
        )
        return {p.name[len("state.") : -len(".json")]: p for p in files}

    @app.get("/api/runs")
    def runs() -> dict:
        return {"runs": ["live", *saved_runs()]}

    @app.get("/api/runs/{name}")
    def run(name: str) -> dict:
        if name == "live":
            rows = [i.model_dump() for i in hub.items.values()]
        else:
            path = saved_runs().get(name)  # only listed files, so no path traversal
            if path is None:
                raise HTTPException(status_code=404, detail="Unknown run")
            rows = json.loads(path.read_text(encoding="utf-8"))
        return {"name": name, "items": [compact(row) for row in rows]}

    @app.get("/api/config")
    def gateway_config() -> dict:
        return {
            "folder": str(config.video_dir) if config.video_dir else None,
            "labels": len(labels),
        }

    @app.get("/api/state")
    def state() -> dict:
        return hub.snapshot()

    @app.post("/api/upload", status_code=202)
    async def upload(files: list[UploadFile]) -> dict:
        names = [f.filename or "" for f in files]
        bad = [n for n in names if video_suffix(n) is None]
        if not files or bad:
            raise HTTPException(
                status_code=415,
                detail=f"Only {', '.join(VIDEO_SUFFIXES)} files are accepted: {bad}",
            )
        ids = []
        for upload_file in files:
            item = new_item(upload_file.filename or "", "upload")
            path = uploaded_path(item)
            with path.open("xb") as output:
                while chunk := await upload_file.read(1024 * 1024):
                    output.write(chunk)
            # Kept for the replay player. shortcut: temp files grow until the gateway restarts,
            # add a cap if this runs for more than a demo session.
            await app.state.runner.enqueue(item, path, delete_after=False)
            ids.append(item.id)
        return {"queued": ids}

    @app.post("/api/run-folder", status_code=202)
    async def run_folder() -> dict:
        if config.video_dir is None or not config.video_dir.is_dir():
            raise HTTPException(status_code=409, detail="VIDEO_DIR is not set on the gateway")
        paths = sorted(
            (p for p in config.video_dir.iterdir() if video_suffix(p.name)),
            key=lambda p: (int(k[2:]) if (k := clip_key(p.name)) else 10**6, p.name),
        )
        for path in paths:
            await app.state.runner.enqueue(new_item(path.name, "folder"), path, delete_after=False)
        return {"queued": len(paths)}

    def uploaded_path(item: Item) -> Path:
        return upload_dir / f"{item.id}{video_suffix(item.name)}"

    def known_item(item_id: str) -> Item:
        item = hub.items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Unknown item")
        return item

    @app.get("/api/items/{item_id}/video")
    def item_video(item_id: str) -> FileResponse:
        item = known_item(item_id)
        if item.source == "folder" and config.video_dir is not None:
            path = config.video_dir / Path(item.name).name
        else:
            path = uploaded_path(item)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Video file is no longer available")
        return FileResponse(path, media_type=MEDIA_TYPES[path.suffix.lower()])

    @app.get("/api/items/{item_id}/trace")
    async def item_trace(item_id: str) -> Response:
        item = known_item(item_id)
        if item.job_id is None:
            raise HTTPException(status_code=404, detail="Item has no checker job")
        response = await app.state.runner.client.get(f"/api/v1/jobs/{item.job_id}/trace")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return Response(response.content, media_type="application/json")

    # ---- annotation: hand-written timelines per clip, scored against a run's traces ----

    def annotation_store() -> AnnotationStore:
        if config.state_file is None:
            raise HTTPException(status_code=409, detail="STATE_FILE is not set; nowhere to save")
        return AnnotationStore(config.state_file.parent / "annotations")

    def folder_clips() -> dict[str, Path]:
        """Clip key -> video file, for every video in VIDEO_DIR (the only annotatable clips)."""
        if config.video_dir is None or not config.video_dir.is_dir():
            return {}
        clips: dict[str, Path] = {}
        for path in sorted(config.video_dir.iterdir()):
            key = clip_key(path.name)
            if video_suffix(path.name) and key:
                clips.setdefault(key, path)
        return dict(sorted(clips.items(), key=lambda kv: int(kv[0][2:])))

    def known_clip(key: str) -> Path:
        path = folder_clips().get(key)  # only listed keys, so no path traversal
        if path is None:
            raise HTTPException(status_code=404, detail="Unknown clip")
        return path

    @app.get("/annotate")
    def annotate_page() -> FileResponse:
        return FileResponse(STATIC / "annotate.html")

    @app.get("/api/annotation-vocabulary")
    def annotation_vocabulary() -> dict:
        return vocabulary()

    @app.get("/api/clips")
    def clips() -> dict:
        saved = {a.clip: a for a in annotation_store().all()} if config.state_file else {}
        return {
            "clips": [
                {
                    "key": key,
                    "name": path.name,
                    "label": labels.get(key),
                    "rows": len(saved[key].rows) if key in saved else 0,
                    "status": saved[key].status if key in saved else None,
                    "annotator": saved[key].annotator if key in saved else "",
                }
                for key, path in folder_clips().items()
            ]
        }

    @app.get("/api/clips/{key}/video")
    def clip_video(key: str) -> FileResponse:
        path = known_clip(key)
        return FileResponse(path, media_type=MEDIA_TYPES[path.suffix.lower()])

    @app.get("/api/annotations/{key}")
    def get_annotation(key: str) -> Stored:
        known_clip(key)
        return annotation_store().load(key)

    @app.put("/api/annotations/{key}")
    def put_annotation(key: str, base_version: float, annotation: Annotation) -> Stored:
        known_clip(key)
        try:
            return annotation_store().save(key, annotation, base_version)
        except VersionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def run_jobs(run: str) -> dict[str, str]:
        """Clip key -> checker job id for the run's finished items (latest wins)."""
        if run == "live":
            rows = [i.model_dump() for i in hub.items.values()]
        else:
            path = saved_runs().get(run)
            if path is None:
                raise HTTPException(status_code=404, detail="Unknown run")
            rows = json.loads(path.read_text(encoding="utf-8"))
        return {
            key: row["job_id"]
            for row in sorted(rows, key=lambda r: r.get("finished_at") or 0)
            if row.get("status") == "done" and row.get("job_id") and (key := clip_key(row["name"]))
        }

    @app.get("/api/annotations-score")
    async def annotations_score(run: str = "live", clip: str | None = None) -> dict:
        jobs = run_jobs(run)
        wanted = [
            a
            for a in annotation_store().all()
            if (a.clip == clip if clip else a.status == "done") and a.clip in jobs
        ]
        scored, missing = [], []
        for annotation in wanted:
            response = await app.state.runner.client.get(
                f"/api/v1/jobs/{jobs[annotation.clip]}/trace"
            )
            if response.status_code == 200:
                scored.append(score_clip(annotation, trace_events(response.content)))
            else:
                missing.append({"clip": annotation.clip, "status": response.status_code})
        return {
            "run": run,
            "summary": summarize(scored),
            "clips": scored,
            "missing_traces": missing,
        }

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        await socket.send_json(hub.snapshot())
        hub.sockets.add(socket)
        try:
            while True:
                await socket.receive_text()  # clients only listen; this detects disconnects
        except WebSocketDisconnect:
            pass
        finally:
            hub.sockets.discard(socket)

    return app
