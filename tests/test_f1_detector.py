"""Tests for `backend.f1.detector.F1Detector`.

Importing this module must not pull in torch (checked explicitly). Running
the actual perception pipeline needs torch/onnxruntime/opencv and the
downloaded model weights, none of which are available in this sandbox
(SHARED_BRIEF.md), so `detect()` itself is exercised only through its pure
helper functions here; the full run is marked `xfail`/skipped with a reason.
"""

from __future__ import annotations

import json
import sys
import time

import pytest

from backend.config import ROOT, Settings
from backend.f1.detector import (
    F1Detector,
    _extra_template_facts,
    _scalar_facts,
    _support_times,
    models_loadable,
)
from backend.f1.rules import Finding as LegacyFinding
from backend.knowledge import Knowledge
from tests.conftest import HAS_FFMPEG, make_rule, make_video


def test_importing_the_detector_module_never_pulls_in_torch():
    assert "backend.f1.detector" in sys.modules
    assert "torch" not in sys.modules


def test_models_loadable_is_false_without_downloaded_weights(tmp_path):
    settings = Settings(api_key="k", weights_dir=tmp_path / "no-such-weights")
    assert models_loadable(settings) is False


def test_constructor_loads_the_real_f1_codex_and_indexes_rules(tmp_path):
    knowledge = Knowledge.load(ROOT / "knowledge")
    settings = Settings(api_key="k", work_dir=tmp_path)
    detector = F1Detector(settings, knowledge.rules)
    assert "L-NO-CASH-ON-LEAVE" in detector._rules_by_id
    # Disabled rules are indexed (startup checks the whole catalogue) but never evaluated.
    assert detector._rules_by_id["L-NO-BAG-ON-LEAVE"].enabled is False
    assert detector._rules_by_id["K-COLLECTOR-DOC"].enabled is False


def test_constructor_rejects_only_the_enabled_rules(tmp_path):
    # main.py once passed knowledge.enabled_rules(); that must fail loudly, not start.
    knowledge = Knowledge.load(ROOT / "knowledge")
    with pytest.raises(ValueError, match="rule IDs differ"):
        F1Detector(Settings(api_key="k", work_dir=tmp_path), knowledge.enabled_rules())


def _detector(tmp_path, overrides=()) -> F1Detector:
    """The real catalogue, with the given test rules replacing the real ones by ID."""
    rules = {r.rule_id: r for r in Knowledge.load(ROOT / "knowledge").rules}
    rules.update({r.rule_id: r for r in overrides})
    return F1Detector(Settings(api_key="k", work_dir=tmp_path), list(rules.values()))


def test_to_finding_adds_t_start_and_t_end_facts_for_the_generic_case(tmp_path):
    detector = _detector(tmp_path, [make_rule("L-PC-LOCKED")])
    legacy = LegacyFinding("L-PC-LOCKED", 10.0, {"actor_id": "person:1"}, confidence=0.8)
    finding = detector._to_finding(legacy, duration_sec=60.0)
    assert finding.rule_id == "L-PC-LOCKED"
    assert finding.t_anchor == 10.0
    assert finding.facts["t_start"] == 10.0
    assert finding.facts["t_end"] == 10.0
    assert finding.facts["actor_id"] == "person:1"
    assert finding.rank_score == 0.8


def test_to_finding_derives_the_window_from_duration_sec(tmp_path):
    detector = _detector(tmp_path, [make_rule("S-SAFE-CLOSED")])
    legacy = LegacyFinding("S-SAFE-CLOSED", 5.0, {"duration_sec": 4.0})
    finding = detector._to_finding(legacy, duration_sec=60.0)
    assert finding.t_start == 5.0
    assert finding.t_end == 9.0
    assert finding.support_t[0] == 5.0
    assert finding.support_t[-1] == 9.0


def test_to_finding_derives_the_window_from_window_end(tmp_path):
    detector = _detector(tmp_path, [make_rule("A-DOOR-LOCK")])
    legacy = LegacyFinding("A-DOOR-LOCK", 2.0, {"window_end": 7.0})
    finding = detector._to_finding(legacy, duration_sec=60.0)
    assert finding.t_end == 7.0


def test_to_finding_clamps_the_window_to_the_video_duration(tmp_path):
    detector = _detector(tmp_path, [make_rule("S-SAFE-CLOSED")])
    legacy = LegacyFinding("S-SAFE-CLOSED", 58.0, {"duration_sec": 10.0})
    finding = detector._to_finding(legacy, duration_sec=60.0)
    assert finding.t_end == 60.0


def test_extra_template_facts_for_cash_left_translates_object_labels():
    rule = make_rule("L-NO-CASH-ON-LEAVE")
    extra = _extra_template_facts("L-NO-CASH-ON-LEAVE", {"track_ids": ["cash:1", "bundle:2"]}, rule)
    assert extra == {"object": "наличные/пачка наличных"}


def test_extra_template_facts_for_cash_left_falls_back_without_track_ids():
    rule = make_rule("L-NO-CASH-ON-LEAVE")
    assert _extra_template_facts("L-NO-CASH-ON-LEAVE", {}, rule) == {"object": "наличные"}


def test_extra_template_facts_for_seal_check_reads_the_rule_param():
    rule = make_rule("K-SEAL-CHECK")
    rule = rule.model_copy(update={"params": {"collector_quick_s": 6.0}})
    assert _extra_template_facts("K-SEAL-CHECK", {}, rule) == {"collector_quick_s": 6.0}


def test_extra_template_facts_is_empty_for_unrelated_rules():
    rule = make_rule("L-PC-LOCKED")
    assert _extra_template_facts("L-PC-LOCKED", {"anything": 1}, rule) == {}


def test_to_finding_carries_the_triggering_object_box(tmp_path):
    detector = _detector(tmp_path, [make_rule("W-NO-PERSONAL-ITEMS")])
    facts = {"object": "handbag", "track_id": "handbag:69", "box": [0.07, 0.5, 0.27, 0.58]}
    legacy = LegacyFinding("W-NO-PERSONAL-ITEMS", 20.0, facts)
    finding = detector._to_finding(legacy, duration_sec=60.0)
    assert [(b.label, b.box) for b in finding.boxes] == [("handbag", (0.07, 0.5, 0.27, 0.58))]


@pytest.mark.parametrize("box", [[], [0.1, 0.2, 0.3], [0.5, 0.5, 0.2, 0.9], "0.1,0.2,0.3,0.4"])
def test_to_finding_has_no_box_when_the_geometry_is_missing_or_degenerate(tmp_path, box):
    detector = _detector(tmp_path, [make_rule("S-SAFE-CLOSED")])
    legacy = LegacyFinding("S-SAFE-CLOSED", 5.0, {"box": box})
    assert detector._to_finding(legacy, duration_sec=60.0).boxes == []


def test_box_label_falls_back_to_the_actor_role(tmp_path):
    detector = _detector(tmp_path, [make_rule("A-OUTSIDER-ZONE")])
    legacy = LegacyFinding("A-OUTSIDER-ZONE", 5.0, {"role": "visitor", "box": [0, 0, 0.5, 1]})
    assert detector._to_finding(legacy, duration_sec=60.0).boxes[0].label == "visitor"


def test_scalar_facts_narrows_lists_to_joined_strings():
    out = _scalar_facts({"track_ids": ["a", "b"], "n": 1, "ok": True, "skip": None})
    assert out == {"track_ids": "a,b", "n": 1, "ok": True}


def test_support_times_is_a_single_point_when_the_window_is_a_point():
    assert _support_times(5.0, 5.0) == [5.0]


def test_support_times_spans_the_window_at_the_step_size():
    times = _support_times(0.0, 2.0)
    assert times[0] == 0.0 and times[-1] == 2.0
    assert len(times) <= 8


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed on this machine")
def test_extract_frames_produces_one_jpeg_per_step(tmp_path):
    video = make_video(tmp_path / "clip.mov", duration=2.0)
    out_dir = tmp_path / "frames"
    out_dir.mkdir()
    frames = F1Detector._extract_frames(video, out_dir, deadline=time.monotonic() + 30)
    assert len(frames) >= 3  # 2s at 2 fps, inclusive of edge rounding


@pytest.mark.skip(
    reason="needs torch/onnxruntime/opencv and downloaded model weights, "
    "not available in this sandbox (SHARED_BRIEF.md); run on datathon2/Docker."
)
def test_detect_runs_end_to_end():
    raise AssertionError("not runnable here")


def test_trace_records_state_changes_roles_and_events(tmp_path):
    from backend.f1.detector import build_trace, write_trace
    from backend.f1.events import EventLog
    from backend.f1.vision_types import Detection, Event, Observation, Scene, State

    person = Detection(
        label="person", score=0.9, box=(0.1, 0.2, 0.3, 0.9), track_id="person:1", role="cashier"
    )
    observations = [
        Observation(
            timestamp_sec=t,
            detections=[person],
            states={"safe": State(value=value, score=0.8, margin=0.2)},
        )
        for t, value in ((0.0, "closed"), (0.5, "closed"), (1.0, "open"))
    ]
    log = EventLog([Event(timestamp_sec=1.0, type="SAFE_OPEN", facts={})], {}, [], {})
    trace = build_trace("ab" * 32, {"cache_hit": True}, 1.5, Scene(objects={}), observations, log)
    assert [(c["t"], c["value"]) for c in trace["state_changes"]] == [
        (0.0, "closed"),
        (1.0, "open"),
    ]
    assert trace["frames"][0]["dets"][0][:3] == ["person", "person:1", "cashier"]
    assert trace["events"][0]["type"] == "SAFE_OPEN" and trace["perception_cache_hit"]
    path = tmp_path / "traces" / "job.json"
    write_trace(path, trace)
    assert json.loads(path.read_text())["video_sha256"] == "ab" * 32


def test_trace_write_failure_is_logged_not_raised(tmp_path, caplog):
    from backend.f1.detector import write_trace

    blocker = tmp_path / "traces"
    blocker.write_text("a file where the directory should be")
    write_trace(blocker / "job.json", {})
    assert "Could not write trace" in caplog.text
