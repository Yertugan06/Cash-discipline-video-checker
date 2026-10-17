import logging
import queue
import shutil
import threading
from pathlib import Path

from backend.config import Settings
from backend.pipeline import AnalysisError, analyze_video
from backend.store import JobStore

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, store: JobStore, settings: Settings):
        self.store = store
        self.settings = settings
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.thread = threading.Thread(target=self.run, name="video-worker", daemon=True)

    def start(self) -> None:
        for job_id in self.store.pending():
            self.queue.put(job_id)
        self.thread.start()

    def stop(self) -> None:
        self.queue.put(None)
        self.thread.join(timeout=self.settings.timeout_sec + 5)

    def run(self) -> None:
        while True:
            job_id = self.queue.get()
            try:
                if job_id is None:
                    return
                row = self.store.get(job_id)
                if row is None:
                    raise RuntimeError(f"Queued job is missing: {job_id}")
                output = self.settings.work_dir / "evidence" / job_id
                if output.exists():
                    shutil.rmtree(output)
                result = analyze_video(
                    Path(row["upload_path"]), output, self.settings, debug=bool(row["debug"])
                )
                self.store.complete(job_id, result)
            except Exception as exc:
                logger.exception("Video job %s failed", job_id)
                message = (
                    str(exc) if isinstance(exc, AnalysisError) else "Internal processing error"
                )
                if job_id is not None:
                    self.store.fail(job_id, message)
            finally:
                self.queue.task_done()
