"""Single FIFO GPU worker thread: one job at a time, per-job deadline, cleanup, TTL purge.

Every job's deadline is absolute: `job_budget_s` after its upload, queue wait
included. A job does not take all of its remaining time when other jobs wait
behind it: `fair_share_s` caps its detection time so that each queued job can
still get an equal part of the time before its own deadline. The pipeline's
finalize reserve is added on top of the share, never past the job's deadline.
A job reached after its deadline (minus `MIN_START_BUDGET_S`) fails as not
analysed.

Every exception that reaches `_process` ends the job as `failed` with a
human-readable message (architecture.md §2, "Job management"). Known,
expected failures (bad media, detector errors, unknown knowledge) surface
their own message; anything else logs the full traceback and reports a
generic message, so internals never leak to API consumers.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from backend.config import Settings
from backend.media import MediaError
from backend.pipeline import IncompleteAnalysisError, Pipeline
from backend.store import JobStore

logger = logging.getLogger(__name__)

# The least time worth starting a job with: the pipeline's finalize reserve plus a short clip.
MIN_START_BUDGET_S = 30.0
VLM_QUEUE_GRACE_S = 60.0
PURGE_INTERVAL_S = 300.0


def _expected_error_types() -> tuple[type[Exception], ...]:
    """Exception types whose message is safe to show the API caller.

    Imports are best-effort: WP2's `backend.vlm.errors` and WP3's
    `backend.knowledge` may not exist yet in this checkout.
    """
    types: list[type[Exception]] = [MediaError, IncompleteAnalysisError]
    try:
        from backend.f1.detector import F1DetectorError

        types.append(F1DetectorError)
    except ModuleNotFoundError:
        pass
    try:
        from backend.vlm.errors import VlmError

        types.append(VlmError)
    except ModuleNotFoundError:
        pass
    try:
        from backend.knowledge import KnowledgeError

        types.append(KnowledgeError)
    except ModuleNotFoundError:
        pass
    return tuple(types)


def fair_share_s(
    own_remaining_s: float, later_remaining_s: list[float], min_start_s: float
) -> float | None:
    """Seconds the current job may use, or None when it can no longer be started.

    `later_remaining_s` is the time left before the deadline of each job queued
    behind this one, in queue order. Running jobs one after another, the k-th
    queued job (this one is the first) starts only after the k-1 before it; it
    keeps an equal share if every job ahead of it uses at most remaining_k / k.
    Jobs that can no longer start are left out. Time a job does not use goes to
    the jobs after it, because each share is computed when its job starts.
    """
    if own_remaining_s < min_start_s:
        return None
    viable = [r for r in later_remaining_s if r >= min_start_s]
    share = own_remaining_s
    for position, remaining in enumerate(viable, start=2):
        share = min(share, remaining / position)
    return min(own_remaining_s, max(share, min_start_s))


class Worker:
    def __init__(self, store: JobStore, settings: Settings, pipeline: Pipeline):
        self.store = store
        self.settings = settings
        self.pipeline = pipeline
        self._expected_errors = _expected_error_types()
        self.queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="video-worker", daemon=True)
        self._purge_thread = threading.Thread(
            target=self._purge_loop, name="result-purge", daemon=True
        )

    def start(self) -> None:
        for job_id in self.store.pending():
            self.queue.put(job_id)
        self.thread.start()
        self._purge_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.queue.put(None)
        self.thread.join(timeout=self.settings.job_budget_s + 30)
        self._purge_thread.join(timeout=5)

    def _run(self) -> None:
        while True:
            job_id = self.queue.get()
            try:
                if job_id is None:
                    return
                self._process(job_id)
            finally:
                self.queue.task_done()

    def _process(self, job_id: str) -> None:
        row = self.store.get(job_id)
        if row is None:
            logger.error("Queued job is missing from the store: %s", job_id)
            return
        video_path = Path(row["upload_path"])
        try:
            wall_elapsed = (datetime.now(UTC) - self.store.created_at(job_id)).total_seconds()
            blocker = self._vlm_unavailable_message(wall_elapsed)
            if blocker is not None:
                self.store.fail(job_id, blocker)
                return
            own_remaining = self.settings.job_budget_s - max(0.0, wall_elapsed)
            share = fair_share_s(own_remaining, self._later_remaining_s(job_id), MIN_START_BUDGET_S)
            if share is None:
                logger.warning(
                    "Video job %s not started: %.0f s in the queue", job_id, wall_elapsed
                )
                self.store.fail(
                    job_id,
                    f"Not analysed: the job waited {wall_elapsed:.0f} s in the queue, "
                    "too long to finish within the time limit",
                )
                return
            logger.info("job %s: %.0f s queued, %.0f s granted", job_id, wall_elapsed, share)
            # The share is detection time; the pipeline's finalize reserve comes on top of it,
            # capped by the job's own absolute deadline.
            deadline = time.monotonic() + min(
                share + self.settings.finalize_reserve_s, own_remaining
            )
            result = self.pipeline.run(job_id, video_path, deadline)
            self.store.complete(job_id, result)
        except self._expected_errors as exc:
            logger.warning("Video job %s failed: %s", job_id, exc)
            self.store.fail(job_id, str(exc))
        except Exception:
            logger.exception("Video job %s failed unexpectedly", job_id)
            self.store.fail(job_id, "Internal processing error")
        finally:
            video_path.unlink(missing_ok=True)

    def _later_remaining_s(self, job_id: str) -> list[float]:
        """Seconds before the deadline of every job queued behind `job_id`, in queue order."""
        pending = self.store.pending()
        later = pending[pending.index(job_id) + 1 :] if job_id in pending else pending
        now = datetime.now(UTC)
        return [
            self.settings.job_budget_s - (now - self.store.created_at(other)).total_seconds()
            for other in later
        ]

    def _vlm_unavailable_message(self, wall_elapsed: float) -> str | None:
        """architecture.md §7: a job stuck in the queue for > 60 s while the
        VLM is not ready fails immediately with a fixed message, instead of
        spending a probe/evidence round trip on a job that cannot succeed."""
        if self.settings.detector != "vlm" or wall_elapsed <= VLM_QUEUE_GRACE_S:
            return None
        try:
            from backend.vlm.client import check_ready
        except ModuleNotFoundError:
            return None
        return None if check_ready(self.settings.vlm) else "model unavailable"

    def _purge_loop(self) -> None:
        while not self._stop.wait(PURGE_INTERVAL_S):
            try:
                self.store.purge_expired(self.settings.results_ttl_hours)
            except Exception:
                logger.exception("Result purge failed")
