"""Real F1 planning -> refined states -> events -> rules, with fake model answers.

These tests establish integration behavior, not real model accuracy.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pytest

from backend.config import ROOT, Settings
from backend.contracts import SamplingPlan, VideoInfo
from backend.f1 import visual_checks as vc
from backend.f1.detector import F1Detector
from backend.f1.events import build_events
from backend.f1.perception import load_perception_config
from backend.f1.vision_types import Detection, Observation, Scene, State
from backend.knowledge import Knowledge


def numeric_scene(duration=10, entry=2):
    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=0.9, box=(0.1, 0.4, 0.8, 0.8)),
            "laptop": Detection(label="laptop", score=0.9, box=(0.2, 0.4, 0.4, 0.6)),
            "door": Detection(label="door", score=0.9, box=(0.85, 0.1, 1, 0.9)),
            "safe": Detection(label="safe", score=0.9, box=(0, 0.1, 0.1, 0.8)),
        },
        confidence=1,
        zones={
            "desk": [(0.1, 0.4), (0.8, 0.4), (0.8, 0.8), (0.1, 0.8)],
            "cashier": [(0, 0), (0.6, 0), (0.6, 0.6), (0, 0.6)],
            "client": [(0.6, 0.1), (1, 0.1), (1, 1), (0.6, 1)],
            "door": [(0.85, 0.1), (1, 0.1), (1, 0.9), (0.85, 0.9)],
        },
    )
    observations = []
    for i in range(duration * 2):
        t = i / 2
        cashier = Detection(
            label="person",
            score=0.9,
            box=(0.2, 0.15, 0.4, 0.55),
            track_id="cashier:1",
            hands=[(0.3, 0.5, 0.9)],
        )
        people = [cashier]
        if t >= entry:
            people.append(
                Detection(
                    label="person",
                    score=0.9,
                    track_id="client:1",
                    box=(0.86, 0.2, 0.98, 0.9) if t < entry + 1 else (0.63, 0.2, 0.8, 0.9),
                )
            )
        observations.append(
            Observation(
                timestamp_sec=t,
                detections=people,
                states={
                    **{f: State(value="closed", score=0.8, margin=0.2) for f in vc.FAMILIES},
                    "cashier:1": State(value="seated", score=0.9, margin=0.4),
                },
            )
        )
    return scene, observations


class StateBackend:
    def __init__(self, door="open", unknown_at=()):
        self.door = door
        self.unknown_at = unknown_at
        self.calls = []

    def identity(self):
        return {"backend": "test_fake_state", "files_sha256": "test-state-v1"}

    def ask(self, frame, request, deadline):
        self.calls.append(request)
        answer = self.door if request.family == "door" and request.observed_entry else "closed"
        if request.family == "door" and request.t in self.unknown_at:
            answer = "unknown"
        return json.dumps({"answer": answer})


def run_detector(
    tmp_path,
    monkeypatch,
    *,
    enabled=True,
    door="open",
    duration=10,
    entry=2,
    unknown_at=(),
):
    from backend.f1 import perception

    video = tmp_path / "synthetic.mov"
    video.write_text("synthetic numeric perception test")
    frames = []
    for i in range(duration * 2):
        frame = tmp_path / f"{i:06d}.jpg"
        frame.write_text(f"synthetic-not-an-image-{i}")
        frames.append(frame)
    scene, observations = numeric_scene(duration, entry)
    config = load_perception_config(ROOT / "config/perception.yaml")
    backend = StateBackend(door, unknown_at)
    monkeypatch.setattr(vc, "_backend", lambda _: backend)
    monkeypatch.setattr(F1Detector, "_extract_frames", lambda *args: frames)
    # The shape the real function returns for a cached, complete run (built per call: tests
    # change `config` after this).
    monkeypatch.setattr(
        perception,
        "perceive_video",
        lambda *args: (
            scene,
            observations,
            {**config, "cache_hit": True, "complete": True, "loop_s": 0.0},
        ),
    )
    settings = Settings(
        api_key="test-only",
        rule_scope="detector",
        work_dir=tmp_path,
        visual_checks=vc.VisualCheckSettings(enabled=enabled, max_checks=24, families=vc.FAMILIES),
    )
    detector = F1Detector(settings, Knowledge.load(ROOT / "knowledge").rules)
    info = VideoInfo(sha256="0" * 64, duration_sec=duration, width=100, height=100, fps=20)
    plan = SamplingPlan(coarse_t=[], fill_t=[], deadline_monotonic=time.monotonic() + 30)
    result = detector.detect(video, info, plan)
    trace = json.loads((settings.traces_dir / "synthetic.json").read_text())
    return result, trace, backend


@pytest.mark.parametrize("door,violation", [("open", False), ("closed", False), ("unknown", False)])
def test_real_detector_keeps_unvalidated_door_answers_diagnostic(
    tmp_path,
    monkeypatch,
    door,
    violation,
):
    result, trace, backend = run_detector(tmp_path, monkeypatch, door=door)
    assert backend.calls
    assert any(f.rule_id == "A-DOOR-LOCK" for f in result.findings) is violation
    checks = [c for c in trace["visual_checks"] if c["family"] == "door" and c["observed_entry"]]
    assert [c["t"] for c in checks] == [6, 6.5, 7]
    assert all(c["diagnostic_only"] and not c["applied"] for c in checks)
    if violation:
        assert any(e["type"] == "DOOR_OPEN" and e["timestamp_sec"] == 6 for e in trace["events"])
        assert all(c["applied"] for c in checks)
    if door == "unknown":
        assert any("checks unknown" in warning for warning in result.warnings)
        assert all(not c["applied"] for c in checks)
    assert all(d[0] == "person" for frame in trace["frames"] for d in frame["dets"])


def test_disabled_detector_has_no_verifier_calls_or_new_trace_keys(tmp_path, monkeypatch):
    result, trace, backend = run_detector(tmp_path, monkeypatch, enabled=False)
    assert not backend.calls
    assert "visual_checks" not in trace
    assert not result.findings
    assert not result.warnings


def test_diagnostic_door_points_do_not_change_rules(tmp_path, monkeypatch):
    result, trace, _ = run_detector(tmp_path, monkeypatch, unknown_at=(6.5,))
    findings = [f for f in result.findings if f.rule_id == "A-DOOR-LOCK"]
    assert not findings
    points = [e for e in trace["events"] if e["type"] == "DOOR_OPEN"]
    assert not points
    assert not any(e["type"] == "EXIT" for e in trace["events"])


@pytest.mark.parametrize("close_at,violation", [(10, True), (3.5, False)])
def test_safe_open_followup_samples_actual_duration_and_clean_closure(
    tmp_path, close_at, violation
):
    from backend.f1.codex import load_codex
    from backend.f1.rules import Context, evaluate_rules

    scene, observations = numeric_scene()
    for observation in observations:
        if observation.timestamp_sec < 2:
            cashier = observation.detections[0]
            cashier.box = (0.0, 0.2, 0.1, 0.7)
            cashier.hands = [(0.05, 0.4, 0.9)]
    config = load_perception_config(ROOT / "config/perception.yaml")
    baseline = build_events(scene, observations, config, 2, 10)
    backend = StateBackend()

    def ask(frame, request, deadline):
        backend.calls.append(request)
        return json.dumps({"answer": "open" if 2 <= request.t < close_at else "closed"})

    backend.ask = ask
    frame = tmp_path / "synthetic-frame"
    frame.write_text("synthetic numeric test, no pixels")
    checks = vc.verify_video(
        frame,
        scene,
        baseline,
        observations,
        options=vc.VisualCheckSettings(enabled=True),
        deadline_monotonic=time.monotonic() + 60,
        duration=10,
        frames=[frame] * 20,
        backend=backend,
    )
    assert len(backend.calls) <= 24
    assert {r.family for r in backend.calls} == {"safe"}
    followups = [c for c in checks if c["trigger"] == "safe_open_window"]
    assert followups and {c["parent_trigger"] for c in followups} == {"safe_departure"}
    assert {c["t"] for c in checks if c["ok"]}.issuperset({2 + i / 2 for i in range(10)})
    refined = vc.apply_checks(observations, checks)
    rebuilt = build_events(scene, refined, config, 2, 10)
    rebuilt = vc.add_verified_state_events(rebuilt, checks)
    context = Context(load_codex(ROOT / "config/f1_codex.yaml"), rebuilt, refined, scene, 10)
    findings = evaluate_rules(context, {"S-SAFE-CLOSED"})
    assert bool(findings) is violation
    assert not any(e.type == "EXIT" for e in rebuilt.events)


def test_recording_cutoff_does_not_create_entry_or_exit_evidence(tmp_path, monkeypatch):
    result, trace, _ = run_detector(tmp_path, monkeypatch, duration=4, entry=0)
    assert not any(f.rule_id in {"A-DOOR-LOCK", "L-PC-LOCKED"} for f in result.findings)
    assert not any(c["observed_entry"] for c in trace["visual_checks"])
    assert not any(e["type"] == "EXIT" for e in trace["events"])


def test_evidence_is_passed_to_context_when_shared_optional_field_exists(tmp_path, monkeypatch):
    from backend.f1 import rules

    original = rules.Context
    captured = []

    @dataclass
    class ContextWithChecks(original):
        visual_checks: list[dict] | None = None

        def __post_init__(self):
            captured.append(self.visual_checks)

    monkeypatch.setattr(rules, "Context", ContextWithChecks)
    result, trace, _ = run_detector(tmp_path, monkeypatch)
    assert captured and captured[0] is not None
    assert len(captured[0]) == len(trace["visual_checks"])
    assert not any("integration pending" in warning for warning in result.warnings)


def test_current_context_contract_gap_is_explicit(tmp_path, monkeypatch):
    from backend.f1.rules import Context

    result, _, _ = run_detector(tmp_path, monkeypatch)
    if not hasattr(Context, "visual_checks"):
        assert any("Context.visual_checks integration pending" in w for w in result.warnings)


def test_rebuilding_after_unknown_answers_does_not_change_baseline_events():
    scene, observations = numeric_scene()
    config = load_perception_config(ROOT / "config/perception.yaml")
    baseline = build_events(scene, observations, config, 2, 10)
    checks = [
        {
            "family": "door",
            "t": 2,
            "box": [0, 0, 1, 1],
            "answer": "unknown",
            "ok": False,
        }
    ]
    refined = vc.apply_checks(observations, checks)
    rebuilt = build_events(scene, refined, config, 2, 10)
    assert rebuilt.events == baseline.events
