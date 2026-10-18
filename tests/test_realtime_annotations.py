"""realtime/annotations.py: the timeline store, matching against trace events, and its endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError

from realtime.annotations import (
    Annotation,
    AnnotationStore,
    Review,
    Row,
    Stored,
    VersionConflict,
    build_suggestions,
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


def test_existing_annotations_load_with_review_defaults(tmp_path):
    store = AnnotationStore(tmp_path)
    store.path("X-3").write_text(
        '{"clip":"X-3","rows":[{"t_start":2,"actor":"client","action":"enter"}]}'
    )
    old = store.load("X-3")
    assert old.rows[0].source == "manual" and not old.rows[0].uncertain
    assert not old.assisted and old.reviews == []


def test_simultaneous_reviewers_cannot_overwrite_the_same_version(tmp_path):
    barrier = Barrier(2)

    def write(name):
        barrier.wait(timeout=5)
        try:
            AnnotationStore(tmp_path).save("X-3", Annotation(summary=name), base_version=0)
        except VersionConflict:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["first reviewer", "second reviewer"]))
    assert sorted(results) == ["conflict", "saved"]
    assert AnnotationStore(tmp_path).load("X-3").summary in {"first reviewer", "second reviewer"}


def test_object_reviews_round_trip_without_inventing_actions_and_keep_provenance(tmp_path):
    store = AnnotationStore(tmp_path)
    review = Review(
        suggestion_id="job:object:0:0",
        run="live",
        kind="object",
        t_start=2,
        label="cash",
        box=(0.1, 0.2, 0.3, 0.4),
        decision="corrected",
        correction="document",
        comment="Cash was missed beside it",
    )
    saved = store.save("X-3", Annotation(reviews=[review]), base_version=0)
    assert saved.assisted and saved.rows == []
    assert store.load("X-3").reviews == [review]
    cleared = store.save("X-3", Annotation(), base_version=saved.version)
    assert cleared.assisted  # revealing predictions cannot later be called blind annotation


def test_review_inputs_reject_invalid_coordinates_and_nonfinite_times():
    with pytest.raises(ValidationError):
        Review(
            suggestion_id="j",
            run="live",
            kind="object",
            t_start=1,
            label="cash",
            box=(0.7, 0.1, 0.2, 0.9),
            decision="accepted",
        )
    with pytest.raises(ValidationError):
        Row(t_start=float("nan"), actor="unknown", action="other")


def test_suggestions_share_the_scorers_event_mapping_and_preserve_object_boxes():
    trace = {
        "duration_sec": 20,
        "events": [
            ev(0, "ENTER", role="cashier", observed_entry=False),
            ev(0, "DOOR_OPEN"),
            ev(3, "ENTER", role="client", observed_entry=True),
            ev(6, "HANDOVER", from_role="client", object="cash"),
        ],
        "frames": [{"t": 3, "dets": [["cash", "cash:1", "unknown", 0.1, 0.2, 0.3, 0.4, 0.8]]}],
    }
    result = build_suggestions(trace, "job42")
    assert [s["row"]["action"] for s in result["events"]] == ["enter", "hand_over"]
    handover = result["events"][1]["row"]
    assert handover["actor"] == "client" and handover["item"] == "cash"
    assert handover["source"] == "suggestion"
    assert result["frames"][0]["objects"][0]["box"] == [0.1, 0.2, 0.3, 0.4]
    assert result == build_suggestions(trace, "job42")
    assert result["events"][0]["id"] != build_suggestions(trace, "different")["events"][0]["id"]


def test_uncertain_notes_are_saved_but_not_scored_as_confirmed_truth():
    truth = timeline({"t_start": 3, "actor": "client", "action": "enter", "uncertain": True})
    scored = score_clip(truth, [])
    assert scored["rows"] == [] and scored["uncertain_notes"] == 1


def test_suggestion_endpoint_uses_selected_run_and_reports_missing_data(tmp_path):
    import json

    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-3.mov").write_bytes(b"clip")
    fake = FakeChecker()
    for name in ("old", "new"):
        (tmp_path / f"state.{name}.json").write_text(
            json.dumps(
                [
                    {
                        "id": name,
                        "name": "X-3.mov",
                        "source": "folder",
                        "status": "done",
                        "job_id": name,
                    }
                ]
            )
        )
        fake.traces[name] = {"events": [ev(3, "EXIT", role="client")]}
    with make_client(
        tmp_path, fake, video_dir=videos, state_file=tmp_path / "state.json"
    ) as client:
        old = client.get("/api/annotation-suggestions/X-3?run=old").json()
        new = client.get("/api/annotation-suggestions/X-3?run=new").json()
        assert old["job_id"] == "old" and new["job_id"] == "new"
        assert old["events"][0]["id"] != new["events"][0]["id"]
        assert client.get("/api/annotation-suggestions/X-99?run=old").status_code == 404
        assert client.get("/api/annotation-suggestions/X-3?run=missing").status_code == 404
        assert client.get("/api/annotation-suggestions/X-3").status_code == 404
        del fake.traces["old"]
        assert client.get("/api/annotation-suggestions/X-3?run=old").status_code == 404
        fake.traces["new"] = {"frames": [{"t": 0, "dets": [["broken"]]}]}
        assert client.get("/api/annotation-suggestions/X-3?run=new").status_code == 502
        assert client.get("/annotate/assets/annotate.js").status_code == 200
        assert client.get("/annotate/assets/annotate.css").status_code == 200
        assert client.get("/annotate/assets/gateway.py").status_code == 422


def test_detect_one_clip_does_not_enqueue_the_whole_folder(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"one")
    (videos / "X-2.mov").write_bytes(b"two")
    fake = FakeChecker()
    with (
        make_client(tmp_path, fake, video_dir=videos, state_file=tmp_path / "state.json") as client,
        client.websocket_connect("/ws") as ws,
    ):
        ws.receive_json()
        response = client.post("/api/clips/X-2/analyze")
        assert response.status_code == 202
        finished = receive_until_finished(ws, 1)
        assert list(finished) == ["X-2.mov"]
        assert client.post("/api/clips/X-99/analyze").status_code == 404
    assert len(fake.uploads) == 1
