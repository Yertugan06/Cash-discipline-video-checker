"""realtime/annotations.py: the timeline store, matching against trace events, and its endpoints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from realtime.annotations import (
    Annotation,
    AnnotationStore,
    Row,
    Stored,
    VersionConflict,
    score_clip,
    summarize,
)
from tests.test_realtime_gateway import FakeChecker, make_client, receive_until_finished


def ev(t, kind, **facts):
    return {"timestamp_sec": t, "type": kind, "facts": facts}


def timeline(*rows, status="done"):
    return Stored(clip="X-3", status=status, rows=[Row(**r) for r in rows])


def test_store_round_trip_and_refuses_a_stale_save(tmp_path):
    store = AnnotationStore(tmp_path / "annotations")
    assert store.load("X-3").version == 0
    first = store.save("X-3", Annotation(summary="client pays"), base_version=0)
    assert store.load("X-3").summary == "client pays"
    with pytest.raises(VersionConflict):
        store.save("X-3", Annotation(summary="someone else"), base_version=0)
    second = store.save("X-3", Annotation(summary="edited"), base_version=first.version)
    assert [a.summary for a in store.all()] == ["edited"] and second.version >= first.version


def test_rows_are_validated():
    with pytest.raises(ValidationError):
        Row(t_start=5, t_end=4, actor="cashier", action="exit")
    with pytest.raises(ValidationError):
        Row(t_start=1, actor="manager", action="exit")


def test_matching_counts_real_entries_roles_and_misses():
    truth = timeline(
        {"t_start": 4.5, "actor": "client", "action": "enter"},
        {"t_start": 9.0, "actor": "client", "action": "hand_over", "item": "cash"},
        {"t_start": 20.0, "actor": "cashier", "action": "open_safe"},
        {"t_start": 22.0, "actor": "cashier", "action": "count_manual"},
    )
    events = [
        ev(0.0, "ENTER", role="cashier", observed_entry=False),  # already in the room
        ev(5.5, "ENTER", role="cashier", observed_entry=True),  # right moment, wrong role
        ev(9.5, "HANDOVER", from_role="client"),
        ev(30.0, "SAFE_OPEN"),  # too late for the ±2 s window
        ev(12.0, "SCREEN", state="working"),  # not a lock
    ]
    scored = score_clip(truth, events)
    rows = {r["action"]: r for r in scored["rows"]}
    assert rows["enter"]["matched_t"] == 5.5 and rows["enter"]["role_ok"] is False
    assert rows["hand_over"]["matched_t"] == 9.5
    assert rows["open_safe"]["matched_t"] is None
    assert rows["count_manual"]["detectable"] is False
    assert [(e["t"], e["action"]) for e in scored["unmatched_events"]] == [(30.0, "open_safe")]

    summary = summarize([scored])
    assert summary["per_action"]["open_safe"] == {
        "truth": 1,
        "found": 0,
        "extra": 1,
        "detectable": True,
    }
    assert summary["roles"] == {"ok": 0, "checked": 1}


def test_one_system_event_cannot_match_two_truth_rows():
    truth = timeline(
        {"t_start": 10.0, "actor": "client", "action": "exit"},
        {"t_start": 11.0, "actor": "client", "action": "exit"},
    )
    scored = score_clip(truth, [ev(10.5, "EXIT", role="client")])
    assert [r["matched_t"] for r in scored["rows"]] == [10.5, None]


def test_annotation_endpoints_and_scoring_against_a_run(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "Х-3.mov").write_bytes(b"clip")
    fake = FakeChecker()
    fake.traces["job1"] = {"events": [ev(5.0, "EXIT", role="cashier")]}
    client = make_client(tmp_path, fake, video_dir=videos, state_file=tmp_path / "state.json")
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/run-folder")
        receive_until_finished(ws, 1)

        assert client.get("/api/clips").json()["clips"][0]["key"] == "X-3"
        assert client.get("/api/clips/X-3/video").content == b"clip"
        assert client.get("/api/clips/X-99/video").status_code == 404
        assert client.get("/api/annotations/..%2F..%2Fstate").status_code == 404

        body = {
            "status": "done",
            "rows": [{"t_start": 4.5, "actor": "cashier", "action": "exit"}],
        }
        saved = client.put("/api/annotations/X-3?base_version=0", json=body)
        assert saved.status_code == 200
        stale = client.put("/api/annotations/X-3?base_version=0", json=body)
        assert stale.status_code == 409
        bad = {"rows": [{"t_start": 4, "t_end": 1, "actor": "cashier", "action": "exit"}]}
        version = saved.json()["version"]
        assert (
            client.put(f"/api/annotations/X-3?base_version={version}", json=bad).status_code == 422
        )

        score = client.get("/api/annotations-score?run=live").json()
    assert (tmp_path / "annotations" / "X-3.json").is_file()
    assert score["summary"]["per_action"]["exit"]["found"] == 1
    assert score["clips"][0]["rows"][0]["role_ok"] is True
    assert score["missing_traces"] == []


def test_scoring_reports_clips_without_a_trace(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"clip")
    client = make_client(
        tmp_path, FakeChecker(), video_dir=videos, state_file=tmp_path / "state.json"
    )
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/run-folder")
        receive_until_finished(ws, 1)
        client.put("/api/annotations/X-1?base_version=0", json={"status": "done"})
        score = client.get("/api/annotations-score?run=live").json()
    assert score["missing_traces"] == [{"clip": "X-1", "status": 404}]


def test_annotation_needs_a_state_file(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"clip")
    with make_client(tmp_path, FakeChecker(), video_dir=videos) as client:
        assert client.get("/api/annotations/X-1").status_code == 409


def test_the_starting_door_and_safe_state_is_not_an_action():
    truth = timeline({"t_start": 12.0, "actor": "cashier", "action": "open_safe"})
    events = [
        ev(0.0, "SAFE_CLOSED"),  # how the clip starts
        ev(0.0, "DOOR_CLOSED"),
        ev(12.5, "SAFE_OPEN"),
        ev(14.0, "DOOR_OPEN"),  # a real later change nobody annotated
    ]
    scored = score_clip(truth, events)
    assert scored["rows"][0]["matched_t"] == 12.5
    assert [(e["t"], e["action"]) for e in scored["unmatched_events"]] == [(14.0, "open_door")]
