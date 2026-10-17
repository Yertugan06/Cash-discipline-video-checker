import socket
import subprocess
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.codex import load_codex, normalize_clip
from backend.config import ROOT, Settings
from backend.evaluation import match_events, parse_timestamp, score
from backend.main import create_app
from backend.pipeline import analyze_video
from backend.store import JobStore
from scripts.export_contract import contract_text


@pytest.fixture
def video(tmp_path, request):
    path = tmp_path / "X-1.mov"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:s=64x96:r=30:d={getattr(request, 'param', 1)}",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def settings(tmp_path, monkeypatch):
    from backend.perception import load_perception_config
    from backend.vision_types import Observation, Scene

    def synthetic_perception(frames, checksum, config, deadline):
        return (
            Scene(objects={}, warnings=["Synthetic test image; no calibrated work area"]),
            [
                Observation(timestamp_sec=i / config.sample_fps, detections=[])
                for i in range(len(frames))
            ],
            load_perception_config(config.perception_config),
        )

    monkeypatch.setattr("backend.perception.perceive_video", synthetic_perception)
    return Settings(api_key="test-only-key", work_dir=tmp_path / "runtime")


def wait_for_job(client, job_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": "test-only-key"})
        assert response.status_code == 200
        if response.json()["status"] != "processing":
            return response.json()
        time.sleep(0.02)
    pytest.fail("Worker did not finish")


def test_api_auth_upload_success_failure_and_persistence(video, settings):
    with TestClient(create_app(settings)) as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            assert client.get("/api/v1/jobs/missing", headers=headers).status_code == 401
            assert (
                client.post(
                    "/api/v1/analyze", files={"file": ("x.mov", b"x")}, headers=headers
                ).status_code
                == 401
            )
        headers = {"X-API-Key": settings.api_key}
        assert client.get("/api/v1/jobs/missing", headers=headers).status_code == 404
        for name, content, status in [("x.mp4", b"x", 415), ("x.mov", b"", 422)]:
            assert (
                client.post(
                    "/api/v1/analyze", files={"file": (name, content)}, headers=headers
                ).status_code
                == status
            )
        response = client.post(
            "/api/v1/analyze?debug=true",
            files={"file": ("../../x.mov", video.read_bytes())},
            headers=headers,
        )
        assert response.status_code == 202
        assert set(response.json()) == {"job_id"}
        job_id = response.json()["job_id"]
        done = wait_for_job(client, job_id)
        assert done["status"] == "done"
        assert done["verdict"] == "no_violation" and done["violations"] == []
        assert done["analysis_stage"] == "complete" and done["warnings"]
        assert done["video"]["sampled_frames"] == 5
        assert client.get(f"/api/v1/jobs/{job_id}/debug", headers=headers).status_code == 200
        response = client.post(
            "/api/v1/analyze", files={"file": ("bad.mov", b"corrupt")}, headers=headers
        )
        failed = wait_for_job(client, response.json()["job_id"])
        assert failed["status"] == "failed" and failed["error"]
        assert "verdict" not in failed
    with TestClient(create_app(settings)) as client:
        assert wait_for_job(client, job_id) == done
    assert {p.name for p in (settings.work_dir / "uploads").iterdir()} == {
        f"{job_id}.mov",
        f"{failed['job_id']}.mov",
    }


def test_size_limit_and_missing_key(settings):
    with pytest.raises(ValueError, match="API_KEY"):
        create_app(replace(settings, api_key=""))
    with TestClient(create_app(replace(settings, max_upload_bytes=2))) as client:
        assert (
            client.post(
                "/api/v1/analyze",
                files={"file": ("x.mov", b"123")},
                headers={"X-API-Key": settings.api_key},
            ).status_code
            == 413
        )
    assert list((settings.work_dir / "uploads").iterdir()) == []


def test_pending_job_recovers_and_pipeline_uses_no_python_network(video, settings, monkeypatch):
    store = JobStore(settings.work_dir / "jobs.sqlite3")
    store.create("recovered", video, False)
    with TestClient(create_app(settings)) as client:
        assert wait_for_job(client, "recovered")["status"] == "done"

    def reject_network(*args, **kwargs):
        raise AssertionError("Network access attempted")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "getaddrinfo", reject_network)
    result = analyze_video(video, settings.work_dir / "offline", settings)
    assert result.video.sampled_frames == 5
    assert {"DECODE_STARTED", "CALIBRATED", "DECODE_COMPLETED"} <= {e.type for e in result.events}


def test_label_parsing_matching_and_scores():
    assert parse_timestamp("1минута 8 секунда") == 68
    assert parse_timestamp("22 секунда") == 22
    assert parse_timestamp(None) is None
    with pytest.raises(ValueError):
        parse_timestamp("tomorrow")
    assert normalize_clip("Х-04.mov") == normalize_clip("#U0425-4.mov") == "X-4"
    assert match_events([10, 12], [11], 2) == [(0, 0)]
    assert match_events([10], [12], 2) == [(0, 0)]
    assert match_events([10], [12.01], 2) == []
    rows = [
        {
            "aliases": ["X-4", "X-47"],
            "labels": [{"timestamp_sec": 57, "rule_ids": []}],
            "result": {"violations": []},
            "status": "done",
            "end_to_end_sec": 1,
        },
        {
            "aliases": ["X-5"],
            "labels": [],
            "result": None,
            "status": "failed",
            "end_to_end_sec": 301,
        },
    ]
    codex = load_codex(ROOT / "codex.yaml")
    summary = score(rows, codex, "smoke")
    assert summary["accuracy"] == 0 and summary["failed"] == 1
    assert summary["labelled_events"] == 1 and summary["hits_2s"] == 0
    assert summary["over_300s"] == 1 and summary["scored_videos"] == 2
    assert score(rows, codex, "weighted", weight_aliases=True)["scored_videos"] == 3


def test_generated_contract_and_real_dataset_deduplication():
    assert (ROOT / "frontend/src/contract.ts").read_text() == contract_text()
    # Dataset assertions run only when local training data is present; never ship it as a fixture.
    if (ROOT / "data/open_labels.xlsx").exists():
        from backend.evaluation import group_videos, read_labels

        codex = load_codex(ROOT / "codex.yaml")
        groups = group_videos(
            ROOT / "data/videos", read_labels(ROOT / "data/open_labels.xlsx"), codex
        )
        assert len(groups) == 40 and sum(len(g.aliases) for g in groups) == 42
        duplicate = next(group for group in groups if "X-4" in group.aliases)
        assert set(duplicate.aliases) == {"X-4", "X-47"}
        assert [event.timestamp_sec for event in duplicate.labels] == [57, 68]


@pytest.mark.parametrize("video", [5], indirect=True)
def test_api_returns_a_complete_violation_with_jpeg_evidence(video, settings, monkeypatch):
    from backend.codex import load_codex
    from backend.perception import load_perception_config
    from backend.vision_types import Detection, Observation, Scene

    def synthetic_coat(frames, checksum, config, deadline):
        desk = Detection(label="desk", score=0.9, box=(0.1, 0.1, 0.9, 0.9))
        scene = Scene(
            objects={"desk": desk}, zones={"desk": [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]}
        )
        observations = [
            Observation(
                timestamp_sec=i / config.sample_fps,
                detections=[
                    Detection(label="coat", score=0.9, box=(0.3, 0.3, 0.6, 0.6), track_id="coat:1")
                ],
            )
            for i in range(len(frames))
        ]
        return scene, observations, load_perception_config(config.perception_config)

    monkeypatch.setattr("backend.perception.perceive_video", synthetic_coat)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": settings.api_key},
            files={"file": ("test.mov", video.read_bytes())},
        )
        done = wait_for_job(client, response.json()["job_id"])
    assert done["status"] == "done" and done["verdict"] == "violation"
    violation = done["violations"][0]
    assert violation["rule_id"] == "W-NO-PERSONAL-ITEMS"
    assert 1 <= len(violation["evidence_frames"]) <= 3
    assert violation["type_en"] and violation["description_en"]
    assert all(frame["image_base64"].startswith("/9j/") for frame in violation["evidence_frames"])
    rule = next(r for r in load_codex(settings.codex_path).rules if r.id == violation["rule_id"])
    assert violation["source"] == rule.source and violation["source_url"] == rule.source_url
