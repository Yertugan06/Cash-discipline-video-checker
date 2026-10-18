"""Regression from the X-4/X-47 event timeline to the jury JSON response."""

from backend.config import ROOT, Settings
from backend.contracts import Coverage, DetectionResult, EvidenceFrame
from backend.f1.detector import F1Detector
from backend.f1.events import EventLog
from backend.f1.rules import evaluate_rules
from backend.f1.vision_types import Event
from backend.knowledge import Knowledge
from backend.serialize import to_done_job
from tests.test_f1_rules import context


def test_x4_and_x47_both_survive_from_one_timeline_to_jury_json(monkeypatch):
    rules = Knowledge.load(ROOT / "knowledge")
    settings = Settings(api_key="test-key", knowledge_dir=ROOT / "knowledge")
    detector = F1Detector(settings, rules.rules)
    base = context()
    events = [
        Event(
            type="CASH_STATE",
            timestamp_sec=50,
            facts={
                "cash_id": "cash-1",
                "session_id": "client-1",
                "location": "desk",
                "track_id": "cash:1",
            },
        ),
        Event(
            type="SESSION_START",
            timestamp_sec=57,
            facts={"session_id": "client-2", "actor_id": "person:2"},
        ),
        Event(
            type="HANDOVER",
            timestamp_sec=68,
            facts={
                "session_id": "client-2",
                "from_id": "person:2",
                "from_role": "client",
                "object": "cash",
            },
        ),
    ]
    base.log = EventLog(events, base.log.coverage, [], {})
    base.log.sessions = {
        "client-2": {
            "client_id": "person:2",
            "start": 57,
            "end": 70,
            "observed_entry": False,
            "cash_ids": [],
            "counted_cash_ids": [],
        }
    }
    base.duration = 80
    monkeypatch.setattr(base, "on_desk", lambda *_args: [base.observations[0].detections[0]])

    active_ids = {rule.rule_id for rule in rules.enabled_rules()}
    legacy = evaluate_rules(base, active_ids)
    findings = [detector._to_finding(item, 80) for item in legacy]
    grounded = rules.ground(findings)
    frames = [
        [EvidenceFrame(timestamp_sec=f.t_anchor, image_base64="/9j/4AAQSkZJRgABAQAAAQABAAD/2Q==")]
        for f in findings
    ]
    result = DetectionResult(
        findings=findings,
        coverage=Coverage(
            step_s=0.5,
            planned=160,
            done=160,
            failed=0,
            deadline_hit=False,
            mode="full",
        ),
        warnings=[],
    )

    payload = to_done_job("x-4", grounded, result, frames, rules.describe).model_dump(mode="json")
    assert payload["verdict"] == "violation"
    assert [v["rule_id"] for v in payload["violations"]] == [
        "S-CLEAN-DESK-HANDOVER",
        "S-NO-MERGE",
    ]
    assert [v["timecode_sec"] for v in payload["violations"]] == [57.0, 68.0]
    assert all(v["jurisdiction"] == "KZ" for v in payload["violations"])
    assert all(v["citation_status"] == "pending" for v in payload["violations"])
