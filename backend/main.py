"""FastAPI app: thin handlers only; all domain logic lives in pipeline/worker/store.

Importing this module must stay cheap (no torch): heavy detector wiring
happens lazily, inside `_build_pipeline`, which only runs when the app
actually starts (the lifespan), never at import time.
"""

import asyncio
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.contracts import AcceptedJob, DoneJob, FailedJob, JobResult, ProcessingJob
from backend.pipeline import Pipeline
from backend.store import JobStore
from backend.worker import Worker


def _build_pipeline(config: Settings) -> Pipeline:
    """Wire the real detector/rank/knowledge collaborators. Only called from
    the lifespan, so `import backend.main` never needs these modules."""
    from backend.knowledge import Knowledge
    from backend.rules import rank

    knowledge = Knowledge.load(config.knowledge_dir)
    if config.detector == "f1":
        from backend.f1.detector import F1Detector

        # F1 checks the whole catalogue against its config and evaluates the enabled rules.
        detector = F1Detector(config, knowledge.rules)
    else:
        from backend.vlm.detector import VlmDetector

        detector = VlmDetector(config.vlm, knowledge.enabled_rules())
    return Pipeline(detector=detector, rank=rank, knowledge=knowledge)


def _is_ready(config: Settings) -> bool:
    if config.detector == "vlm":
        try:
            from backend.vlm.client import check_ready
        except ModuleNotFoundError:
            return False
        return check_ready(config.vlm)
    from backend.f1.detector import models_loadable

    return models_loadable(config)


def create_app(settings: Settings | None = None, *, pipeline: Pipeline | None = None) -> FastAPI:
    """Build the FastAPI app. `pipeline` lets tests inject fake collaborators
    without needing WP2's/WP3's real modules to exist."""
    config = settings or Settings.from_env()
    # uvicorn only configures its own loggers; without this the per-stage job log is dropped.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = JobStore(config.work_dir / "jobs.sqlite3")
        active_pipeline = pipeline if pipeline is not None else _build_pipeline(config)
        worker = Worker(store, config, active_pipeline)
        app.state.store = store
        app.state.worker = worker
        app.state.settings = config
        worker.start()
        try:
            yield
        finally:
            await asyncio.to_thread(worker.stop)

    app = FastAPI(
        title="Forte cash discipline checker",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def authenticate(key: Annotated[str | None, Depends(header)]) -> None:
        if key is None or not secrets.compare_digest(key.encode(), config.api_key.encode()):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    health_router = APIRouter()

    @health_router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @health_router.get("/readyz")
    def readyz() -> JSONResponse:
        ready = _is_ready(config)
        return JSONResponse(
            {"status": "ok" if ready else "not_ready"}, status_code=200 if ready else 503
        )

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

    @router.post("/analyze", response_model=AcceptedJob, status_code=202)
    def analyze(request: Request, file: UploadFile) -> AcceptedJob:
        if not file.filename or not file.filename.lower().endswith(".mov"):
            raise HTTPException(status_code=415, detail="Only .mov files are accepted")
        job_id = uuid4().hex
        uploads = config.work_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        destination = uploads / f"{job_id}.mov"
        size = 0
        try:
            with destination.open("xb") as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > config.max_upload_bytes:
                        raise HTTPException(
                            status_code=413, detail="Video exceeds upload size limit"
                        )
                    output.write(chunk)
            if size == 0:
                raise HTTPException(status_code=422, detail="Video is empty")
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()
        request.app.state.store.create(job_id, destination)
        request.app.state.worker.queue.put(job_id)
        return AcceptedJob(job_id=job_id)

    @router.get("/jobs/{job_id}", response_model=JobResult)
    def get_job(request: Request, job_id: str) -> ProcessingJob | DoneJob | FailedJob:
        row = request.app.state.store.get(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if row["status"] == "done":
            return DoneJob(job_id=job_id, status="done", **json.loads(row["result_json"]))
        if row["status"] == "failed":
            return FailedJob(job_id=job_id, status="failed", error=row["error"])
        return ProcessingJob(job_id=job_id, status="processing")

    @router.get("/jobs/{job_id}/trace")
    def get_trace(job_id: str) -> FileResponse:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise HTTPException(status_code=404, detail="Trace not found")
        path = config.traces_dir / f"{job_id}.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Trace not found")
        return FileResponse(path, media_type="application/json")

    app.include_router(health_router)
    app.include_router(router)
    if config.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=config.frontend_dist, html=True), name="ui")
    return app
