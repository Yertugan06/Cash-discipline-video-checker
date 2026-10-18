"""API/worker/store tests. A `FakePipeline` (see conftest.py) is injected into
`create_app` so these never need ffmpeg or the real detector/knowledge
modules -- except the one test that specifically checks a corrupt upload is
rejected by the real `backend.media.probe`, which is gated on ffmpeg/ffprobe
being installed.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.contracts import Coverage, DoneJob
from backend.main import create_app
from backend.pipeline import Pipeline
from backend.store import JobStore
from backend.worker import MIN_START_BUDGET_S, Worker, fair_share_s
from tests.conftest import FakeDetector, FakeKnowledge, FakePipeline, identity_rank, requires_ffmpeg

API_KEY = "test-only-key"


@pytest.fixture
def settings(tmp_path):
    # Empty weights dir: readiness must not depend on whether this machine has weights downloaded.
    return Settings(
        api_key=API_KEY, work_dir=tmp_path / "runtime", detector="f1", weights_dir=tmp_path / "w"
    )


def done_job(job_id: str = "will-be-overwritten", *, violations=None) -> DoneJob:
    return DoneJob(
        job_id=job_id,
        status="done",
        verdict="violation" if violations else "no_violation",
        violations=violations or [],
        warnings=[],
        coverage=Coverage(
            step_s=0.5, planned=10, done=10, failed=0, deadline_hit=False, mode="full"
        ),
    )


def wait_for_job(client: TestClient, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY})
        assert response.status_code == 200
        if response.json()["status"] != "processing":
            return response.json()
        time.sleep(0.02)
    pytest.fail("Worker did not finish in time")


def upload(
    client: TestClient, filename: str = "x.mov", content: bytes = b"not really a video"
) -> object:
    return client.post(
        "/api/v1/analyze", files={"file": (filename, content)}, headers={"X-API-Key": API_KEY}
    )


# --- auth ------------------------------------------------------------------


def test_missing_or_wrong_key_is_rejected(settings):
    fake = FakePipeline(result=done_job())
    with TestClient(create_app(settings, pipeline=fake)) as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            assert client.get("/api/v1/jobs/anything", headers=headers).status_code == 401
            assert (
                client.post(
                    "/api/v1/analyze", files={"file": ("x.mov", b"x")}, headers=headers
                ).status_code
                == 401
            )


def test_health_and_ready_need_no_key(settings):
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        assert client.get("/healthz").status_code == 200
        # f1 mode, no weights downloaded in this tmp settings -> not ready.
        assert client.get("/readyz").status_code == 503


# --- upload validation -------------------------------------------------------


def test_non_video_upload_is_rejected_415(settings):
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        for name in ("x.avi", "x.txt", "mov", "x"):
            assert upload(client, name).status_code == 415


@pytest.mark.parametrize("name", ["x.mov", "x.mp4", "x.mkv", "X.MP4"])
def test_mov_mp4_mkv_uploads_are_accepted(settings, name):
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        response = upload(client, name)
        assert response.status_code == 202
        stored = list((settings.work_dir / "uploads").iterdir())
        assert [p.suffix for p in stored] == [name[1:].lower()]


def test_empty_upload_is_rejected_422(settings):
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        assert upload(client, "x.mov", b"").status_code == 422


def test_oversize_upload_is_rejected_413(settings):
    small_limit = replace(settings, max_upload_bytes=4)
    with TestClient(create_app(small_limit, pipeline=FakePipeline(result=done_job()))) as client:
        assert upload(client, "x.mov", b"123456").status_code == 413
    assert list((small_limit.work_dir / "uploads").iterdir()) == []


def test_missing_job_is_404(settings):
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        response = client.get("/api/v1/jobs/does-not-exist", headers={"X-API-Key": API_KEY})
        assert response.status_code == 404


# --- happy path: 202 -> processing -> done, validated against the contract --


def test_accepted_then_processing_then_done_matches_the_contract(settings):
    violations = []
    fake = FakePipeline(result=None)

    def run(job_id, video, deadline_monotonic):
        fake.calls.append((job_id, video, deadline_monotonic))
        return done_job(job_id, violations=violations)

    fake.run = run  # type: ignore[method-assign]
    with TestClient(create_app(settings, pipeline=fake)) as client:
        response = upload(client)
        assert response.status_code == 202
        assert set(response.json()) == {"job_id"}
        job_id = response.json()["job_id"]
        payload = wait_for_job(client, job_id)
    assert payload["status"] == "done"
    validated = DoneJob.model_validate(payload)
    assert validated.job_id == job_id
    assert validated.verdict == "no_violation"


# --- deadline wiring ---------------------------------------------------------


def test_deadline_passed_to_the_pipeline_reflects_job_budget(settings):
    fake = FakePipeline(result=done_job())
    before = time.monotonic()
    with TestClient(create_app(settings, pipeline=fake)) as client:
        response = upload(client)
        wait_for_job(client, response.json()["job_id"])
    assert len(fake.calls) == 1
    _, _, deadline = fake.calls[0]
    assert before + settings.job_budget_s - 1 <= deadline <= before + settings.job_budget_s + 5


def test_fair_share_alone_gets_all_remaining_time():
    assert fair_share_s(270.0, [], 30.0) == 270.0


def test_fair_share_splits_time_between_jobs_uploaded_together():
    # Five jobs uploaded at once: run one after another, each must fit in 270 / 5 s.
    assert fair_share_s(270.0, [270.0] * 4, 30.0) == pytest.approx(54.0)


def test_fair_share_uses_the_tightest_later_deadline():
    # The job behind has only 100 s left: this job and that one get 50 s each.
    assert fair_share_s(260.0, [100.0, 250.0], 30.0) == pytest.approx(50.0)


def test_fair_share_ignores_later_jobs_that_cannot_start_anyway():
    assert fair_share_s(200.0, [20.0], 30.0) == 200.0


def test_fair_share_never_goes_below_the_minimum_start_budget():
    assert fair_share_s(270.0, [270.0] * 20, 30.0) == 30.0


def test_fair_share_refuses_a_job_whose_deadline_has_nearly_passed():
    assert fair_share_s(29.0, [], 30.0) is None


def test_later_remaining_lists_only_the_jobs_queued_behind(settings, tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    for job_id in ("first", "second", "third"):
        store.create(job_id, tmp_path / f"{job_id}.mov")
    worker = Worker(store, settings, FakePipeline(result=done_job()))
    remaining = worker._later_remaining_s("second")
    assert len(remaining) == 1
    assert settings.job_budget_s - 5 <= remaining[0] <= settings.job_budget_s


def test_job_reached_after_its_deadline_fails_as_not_analysed(settings):
    # A budget below MIN_START_BUDGET_S stands in for a job that waited too long in the queue.
    tight = replace(settings, job_budget_s=MIN_START_BUDGET_S - 10)
    fake = FakePipeline(result=done_job())
    with TestClient(create_app(tight, pipeline=fake)) as client:
        response = upload(client)
        payload = wait_for_job(client, response.json()["job_id"])
    assert payload["status"] == "failed"
    assert payload["error"].startswith("Not analysed")
    assert fake.calls == []


# --- failure handling ---------------------------------------------------------


def test_pipeline_error_fails_the_job_with_its_message(settings):
    fake = FakePipeline(error=ValueError("the video has no readable stream"))
    with TestClient(create_app(settings, pipeline=fake)) as client:
        response = upload(client)
        payload = wait_for_job(client, response.json()["job_id"])
    assert payload["status"] == "failed"
    assert "verdict" not in payload
    assert payload["error"]


@requires_ffmpeg
def test_a_corrupt_video_fails_through_the_real_probe(settings):
    pipeline = Pipeline(detector=FakeDetector(), rank=identity_rank, knowledge=FakeKnowledge())
    with TestClient(create_app(settings, pipeline=pipeline)) as client:
        response = upload(client, "bad.mov", b"this is not a real quicktime file")
        payload = wait_for_job(client, response.json()["job_id"])
    assert payload["status"] == "failed"
    assert payload["error"]


# --- cleanup and restart ------------------------------------------------------


def test_upload_is_deleted_once_the_job_ends(settings):
    fake = FakePipeline(result=done_job())
    with TestClient(create_app(settings, pipeline=fake)) as client:
        response = upload(client)
        wait_for_job(client, response.json()["job_id"])
    assert list((settings.work_dir / "uploads").iterdir()) == []


def test_restart_re_enqueues_a_pending_job(settings):
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    upload_path = settings.work_dir / "uploads"
    upload_path.mkdir(parents=True, exist_ok=True)
    video_path = upload_path / "recovered.mov"
    video_path.write_bytes(b"placeholder")
    store = JobStore(settings.work_dir / "jobs.sqlite3")
    store.create("recovered", video_path)
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        payload = wait_for_job(client, "recovered")
    assert payload["status"] == "done"
    assert not video_path.exists()


# --- result TTL purge ---------------------------------------------------------


def test_purge_expired_removes_old_finished_rows_but_keeps_fresh_ones(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("old", tmp_path / "old.mov")
    store.complete("old", done_job("old"))
    store.create("fresh", tmp_path / "fresh.mov")
    store.complete("fresh", done_job("fresh"))
    old_timestamp = (datetime.now(UTC) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET created_at = ? WHERE job_id = 'old'", (old_timestamp,))
    removed = store.purge_expired(ttl_hours=24)
    assert removed == 1
    assert store.get("old") is None
    assert store.get("fresh") is not None


def test_trace_is_served_by_job_id_and_guarded(settings):
    job_id = "a" * 32
    settings.traces_dir.mkdir(parents=True)
    (settings.traces_dir / f"{job_id}.json").write_text('{"frames": []}')
    headers = {"X-API-Key": API_KEY}
    with TestClient(create_app(settings, pipeline=FakePipeline(result=done_job()))) as client:
        assert client.get(f"/api/v1/jobs/{job_id}/trace").status_code == 401
        found = client.get(f"/api/v1/jobs/{job_id}/trace", headers=headers)
        missing = client.get(f"/api/v1/jobs/{'b' * 32}/trace", headers=headers)
        traversal = client.get("/api/v1/jobs/..%2Fjobs.sqlite3/trace", headers=headers)
    assert found.status_code == 200 and found.json() == {"frames": []}
    assert missing.status_code == 404
    assert traversal.status_code == 404
