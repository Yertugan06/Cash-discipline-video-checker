import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from backend.codex import load_codex
from backend.config import Settings
from backend.models import AcceptedJob, DoneJob, FailedJob, ProcessingJob
from backend.store import JobStore
from backend.worker import Worker


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_codex(config.codex_path)
        store = JobStore(config.work_dir / "jobs.sqlite3")
        worker = Worker(store, config)
        app.state.store = store
        app.state.worker = worker
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

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

    @router.post("/analyze", response_model=AcceptedJob, status_code=202)
    def analyze(request: Request, file: UploadFile, debug: bool = False) -> AcceptedJob:
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
            request.app.state.store.create(job_id, destination, debug)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()
        request.app.state.worker.queue.put(job_id)
        return AcceptedJob(job_id=job_id)

    @router.get("/jobs/{job_id}", response_model=ProcessingJob | DoneJob | FailedJob)
    def get_job(request: Request, job_id: str):
        row = request.app.state.store.get(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if row["status"] == "done":
            return DoneJob(job_id=job_id, **json.loads(row["result_json"]))
        if row["status"] == "failed":
            return FailedJob(job_id=job_id, error=row["error"])
        return ProcessingJob(job_id=job_id)

    @router.get("/jobs/{job_id}/debug")
    def get_debug(request: Request, job_id: str):
        row = request.app.state.store.get(job_id)
        if row is None or row["status"] != "done" or not row["debug"]:
            raise HTTPException(status_code=404, detail="Debug video not available")
        return FileResponse(config.work_dir / "evidence" / row["job_id"] / "debug.mp4")

    app.include_router(router)
    if config.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=config.frontend_dist, html=True), name="ui")
    return app
