"""Draft provenance, safe retrieval, and description-only review without invented times."""

import json

import pytest
from pydantic import ValidationError

from realtime.annotations import Annotation, AnnotationStore
from realtime.descriptions import DescriptionDraft, write_draft
from tests.test_realtime_gateway import FakeChecker, make_client, receive_until_finished


def ready(clip="X-1"):
    return DescriptionDraft(
        clip=clip,
        status="ready",
        description="Synthetic description for endpoint tests.",
        model="test-local-model",
        sampled_timestamps=[0, 1, 2, 3],
    )


def test_ready_drafts_require_model_text_and_valid_sample_times():
    with pytest.raises(ValidationError):
        DescriptionDraft(clip="X-1", status="ready")
    with pytest.raises(ValidationError):
        DescriptionDraft.model_validate(
            ready().model_dump() | {"sampled_timestamps": [float("nan")]}
        )
    with pytest.raises(ValidationError):
        DescriptionDraft(clip="../X-1", status="queued")
    with pytest.raises(ValidationError):
        DescriptionDraft(clip="X-1", status="failed")


def test_description_retrieval_is_separate_from_human_annotations(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"synthetic fixture")
    store = AnnotationStore(tmp_path / "annotations")
    saved = store.save("X-1", Annotation(summary="Human correction"), base_version=0)
    with make_client(
        tmp_path, FakeChecker(), video_dir=videos, state_file=tmp_path / "state.json"
    ) as client:
        assert client.get("/api/annotation-description/X-1").json()["status"] == "unavailable"
        write_draft(tmp_path / "descriptions", ready())
        response = client.get("/api/annotation-description/X-1")
        assert response.status_code == 200
        assert response.json()["description"] == ready().description
        assert client.get("/api/annotation-description/X-99").status_code == 404
        assert client.get("/api/annotation-description/..%2Fstate").status_code == 404
        write_draft(tmp_path / "descriptions", DescriptionDraft(clip="X-1", status="processing"))
        assert client.get("/api/annotation-description/X-1").json()["status"] == "processing"
    assert store.load("X-1") == saved


def test_invalid_drafts_are_reported_explicitly(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"synthetic fixture")
    drafts = tmp_path / "descriptions"
    drafts.mkdir()
    path = drafts / "X-1.json"
    path.write_text(json.dumps(ready("X-2").model_dump()))
    with make_client(
        tmp_path, FakeChecker(), video_dir=videos, state_file=tmp_path / "state.json"
    ) as client:
        assert client.get("/api/annotation-description/X-1").status_code == 500
        path.write_text("{broken")
        assert client.get("/api/annotation-description/X-1").status_code == 500


def test_description_corrections_keep_ai_provenance_and_need_no_timestamps(tmp_path):
    store = AnnotationStore(tmp_path)
    first = store.save(
        "X-1",
        Annotation(
            summary="A corrected whole-clip description. " * 80,
            description_source="ai_draft",
            description_model="test-local-model",
            status="done",
        ),
        base_version=0,
    )
    assert first.assisted and first.rows == []
    assert first.description_model == "test-local-model"
    assert store.load("X-1").summary == first.summary
    second = store.save("X-1", Annotation(summary="A later edit"), base_version=first.version)
    assert second.assisted


def test_descriptions_without_times_do_not_produce_false_event_scores(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "X-1.mov").write_bytes(b"synthetic fixture")
    fake = FakeChecker()
    client = make_client(tmp_path, fake, video_dir=videos, state_file=tmp_path / "state.json")
    with client, client.websocket_connect("/ws") as ws:
        ws.receive_json()
        client.post("/api/run-folder")
        receive_until_finished(ws, 1)
        client.put(
            "/api/annotations/X-1?base_version=0",
            json={
                "summary": "A person approaches the desk.",
                "status": "done",
            },
        )
        result = client.get("/api/annotations-score").json()
    assert result["clips"] == []
    assert result["description_only"] == ["X-1"]
    assert result["summary"]["per_action"] == {}
