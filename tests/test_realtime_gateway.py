"""realtime/gateway.py against a fake checker (httpx.MockTransport): no GPU, no real videos."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from realtime.gateway import GatewaySettings, clip_key, create_app, load_labels

DONE = {
    "status": "done",
    "verdict": "violation",
    "violations": [
        {
            "type": "Личные вещи на рабочем месте",
            "timecode_sec": 20.0,
            "description": "test",
            "evidence_frames": [{"timestamp_sec": 20.0, "image_base64": "AA=="}],
        }
    ],
    "warnings": [],
    "coverage": None,
}


class FakeChecker:
    """Answers `processing` for the first `polls_before_done` polls of each job."""

    def __init__(self, *, final: dict | None = None, analyze_status: int = 202):
        self.final = final or DONE
        self.analyze_status = analyze_status
        self.polls: dict[str, int] = {}
        self.uploads: list[tuple[str, str | None]] = []
        self.log: list[str] = []
        self.traces: dict[str, dict] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/analyze":
            self.uploads.append((request.headers["content-type"], request.headers.get("x-api-key")))
            if self.analyze_status != 202:
                return httpx.Response(self.analyze_status, json={"detail": "nope"})
            job_id = f"job{len(self.uploads)}"
            self.log.append("upload")
            self.polls[job_id] = 0
            return httpx.Response(202, json={"job_id": job_id})
        if request.url.path.endswith("/trace"):
            job_id = request.url.path.split("/")[-2]
            if job_id not in self.traces:
                return httpx.Response(404, json={"detail": "Trace not found"})
            return httpx.Response(200, json=self.traces[job_id])
        job_id = request.url.path.rsplit("/", 1)[-1]
        self.polls[job_id] += 1
        if self.polls[job_id] < 3:
            return httpx.Response(200, json={"job_id": job_id, "status": "processing"})
        self.log.append("finished")
        return httpx.Response(200, json={"job_id": job_id, **self.final})


def make_client(
    tmp_path, fake: FakeChecker, *, video_dir=None, labels=None, state_file=None
) -> TestClient:
    settings = GatewaySettings(
        checker_url="http://checker",
        api_key="secret",
        video_dir=video_dir,
        labels_path=labels,
        state_file=state_file,
        poll_s=0.01,
        job_timeout_s=5,
    )
    return TestClient(create_app(settings, transport=httpx.MockTransport(fake)))


def receive_until_finished(ws, count: int) -> dict[str, dict]:
    finished: dict[str, dict] = {}
    while len(finished) < count:
        message = ws.receive_json()
        if message["type"] == "item" and message["item"]["status"] in ("done", "failed"):
            finished[message["item"]["name"]] = message["item"]
    return finished


def test_clip_key_normalises_latin_and_cyrillic_ids():
    assert clip_key("Х-3.mov") == "X-3"  # Cyrillic Х
    assert clip_key("X-003") == "X-3"
    assert clip_key("x 12.MOV") == "X-12"
    assert clip_key("random.mov") is None


def test_load_labels_reads_prepared_videos_jsonl(tmp_path):
    path = tmp_path / "videos.jsonl"
    rows = [
        {"original_id": "X-1", "organizer_verdict": "violation"},
        {"original_id": "Х-3", "organizer_verdict": "no_violation"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    assert load_labels(path) == {"X-1": "violation", "X-3": "no_violation"}
    assert load_labels(None) == {}


def test_upload_streams_status_changes_and_final_verdict_over_websocket(tmp_path):
    fake = FakeChecker()
    labels = tmp_path / "videos.jsonl"
    labels.write_text(json.dumps({"original_id": "X-1", "organizer_verdict": "no_violation"}))
    client = make_client(tmp_path, fake, labels=labels)
    with client, client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "snapshot", "items": []}
        response = client.post(
            "/api/upload", files=[("files", ("X-1.mov", b"fake-bytes", "video/quicktime"))]
        )
        assert response.status_code == 202
        statuses = []
        while not statuses or statuses[-1] not in ("done", "failed"):
            message = ws.receive_json()
            statuses.append(message["item"]["status"])
        item = message["item"]
    assert statuses == ["queued", "submitting", "processing", "done"]
    assert item["verdict"] == "violation"
    assert item["label"] == "no_violation"
    assert item["result"]["violations"][0]["timecode_sec"] == 20.0
    content_type, api_key = fake.uploads[0]
    assert content_type.startswith("multipart/form-data") and api_key == "secret"


def test_upload_rejects_non_mov(tmp_path):
    with make_client(tmp_path, FakeChecker()) as client:
        response = client.post("/api/upload", files=[("files", ("a.mp4", b"x", "video/mp4"))])
    assert response.status_code == 415


@pytest.mark.parametrize(
    ("fake", "error"),
    [
        (FakeChecker(analyze_status=413), "checker 413"),
        (FakeChecker(final={"status": "failed", "error": "Video is corrupt"}), "Video is corrupt"),
    ],
)
def test_checker_failures_are_reported_not_swallowed(tmp_path, fake, error):
    with make_client(tmp_path, fake) as client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/upload", files=[("files", ("X-2.mov", b"x", "video/quicktime"))])
        item = receive_until_finished(ws, 1)["X-2.mov"]
    assert item["status"] == "failed"
    assert error in item["error"]


def test_run_folder_submits_clips_one_at_a_time_in_numeric_order(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    for name in ("X-10.mov", "Х-2.mov", "X-1.mov", "notes.txt"):
        (videos / name).write_bytes(b"x")
    fake = FakeChecker()
    client = make_client(tmp_path, fake, video_dir=videos)
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert client.post("/api/run-folder").json() == {"queued": 3}
        finished = receive_until_finished(ws, 3)
        state = client.get("/api/state").json()["items"]
    assert [i["name"] for i in state] == ["X-1.mov", "Х-2.mov", "X-10.mov"]
    assert all(i["status"] == "done" for i in finished.values())
    # sequential: each job was polled to completion before the next upload
    assert fake.log == ["upload", "finished"] * 3


def test_run_folder_without_video_dir_is_a_clear_error(tmp_path):
    with make_client(tmp_path, FakeChecker()) as client:
        response = client.post("/api/run-folder")
    assert response.status_code == 409


def test_past_results_survive_a_gateway_restart(tmp_path):
    state_file = tmp_path / "state.json"
    client = make_client(tmp_path, FakeChecker(), state_file=state_file)
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/upload", files=[("files", ("X-1.mov", b"x", "video/quicktime"))])
        receive_until_finished(ws, 1)

    client = make_client(tmp_path, FakeChecker(), state_file=state_file)
    with client, client.websocket_connect("/ws") as ws:
        snapshot = ws.receive_json()
    assert [(i["name"], i["status"], i["verdict"]) for i in snapshot["items"]] == [
        ("X-1.mov", "done", "violation")
    ]


def test_restart_requeues_unfinished_folder_clips_and_fails_lost_uploads(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-5.mov").write_bytes(b"x")
    state_file = tmp_path / "state.json"
    rows = [
        {
            "id": "a",
            "name": "X-5.mov",
            "source": "folder",
            "status": "processing",
            "job_id": "old",
            "queued_at": 1.0,
            "started_at": 2.0,
        },
        {"id": "b", "name": "X-6.mov", "source": "upload", "status": "queued", "queued_at": 3.0},
    ]
    state_file.write_text(json.dumps(rows), encoding="utf-8")
    fake = FakeChecker()
    client = make_client(tmp_path, fake, video_dir=videos, state_file=state_file)
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        if client.get("/api/state").json()["items"][0]["status"] != "done":
            receive_until_finished(ws, 1)
        items = {i["id"]: i for i in client.get("/api/state").json()["items"]}
    assert items["a"]["status"] == "done" and items["a"]["job_id"] == "job1"
    assert items["b"]["status"] == "failed"
    assert "restart" in items["b"]["error"]
    assert fake.log == ["upload", "finished"]


def test_replay_serves_the_folder_video_and_proxies_the_trace(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"0123456789")
    fake = FakeChecker()
    fake.traces["job1"] = {"frames": [{"t": 0.0, "dets": []}]}
    client = make_client(tmp_path, fake, video_dir=videos)
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/run-folder")
        item = receive_until_finished(ws, 1)["X-1.mov"]
        video = client.get(f"/api/items/{item['id']}/video", headers={"Range": "bytes=2-5"})
        trace = client.get(f"/api/items/{item['id']}/trace")
    assert video.status_code == 206 and video.content == b"2345"
    assert video.headers["content-type"] == "video/mp4"
    assert trace.status_code == 200 and trace.json() == fake.traces["job1"]


def test_replay_keeps_uploads_and_reports_missing_traces(tmp_path):
    client = make_client(tmp_path, FakeChecker())
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/upload", files=[("files", ("X-2.mov", b"upload", "video/quicktime"))])
        item = receive_until_finished(ws, 1)["X-2.mov"]
        video = client.get(f"/api/items/{item['id']}/video")
        trace = client.get(f"/api/items/{item['id']}/trace")
        unknown = client.get("/api/items/nope/video")
    assert video.status_code == 200 and video.content == b"upload"
    assert trace.status_code == 404
    assert unknown.status_code == 404


def test_folder_run_with_a_state_file_survives_overlapping_saves(tmp_path, monkeypatch):
    original_replace = Path.replace

    def slow_replace(self, target):  # writing a multi-MB state file leaves this window on the VM
        time.sleep(0.02)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", slow_replace)

    videos = tmp_path / "videos"
    videos.mkdir()
    for n in range(1, 13):
        (videos / f"X-{n}.mov").write_bytes(b"x")
    state = tmp_path / "state.json"
    client = make_client(tmp_path, FakeChecker(), video_dir=videos, state_file=state)
    with client:
        assert client.post("/api/run-folder").json() == {"queued": 12}
    assert len(json.loads(state.read_text())) == 12


def test_compare_lists_saved_runs_and_serves_them_without_evidence(tmp_path):
    state = tmp_path / "state" / "state.json"
    state.parent.mkdir()
    saved = [
        {
            "id": "a",
            "name": "X-1.mov",
            "source": "folder",
            "status": "done",
            "verdict": "violation",
            "label": "no_violation",
            "started_at": 10.0,
            "finished_at": 12.5,
            "result": {"job_id": "j", **DONE},
        }
    ]
    (state.parent / "state.before-fix.json").write_text(json.dumps(saved))
    with make_client(tmp_path, FakeChecker(), state_file=state) as client:
        names = client.get("/api/runs").json()["runs"]
        run = client.get("/api/runs/before-fix").json()
        live = client.get("/api/runs/live").json()
        unknown = client.get("/api/runs/..%2F..%2Fetc").status_code
        page = client.get("/compare")
    assert names == ["live", "before-fix"]
    assert run["items"] == [
        {
            "name": "X-1.mov",
            "label": "no_violation",
            "status": "done",
            "verdict": "violation",
            "error": None,
            "seconds": 2.5,
            "violations": [
                {"rule_id": None, "type": DONE["violations"][0]["type"], "timecode_sec": 20.0}
            ],
        }
    ]
    assert live == {"name": "live", "items": []}
    assert unknown == 404
    assert page.status_code == 200 and "Compare runs" in page.text
