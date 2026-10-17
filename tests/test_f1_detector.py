"""Tests for `backend.f1.detector.F1Detector`.

Importing this module must not pull in torch (checked explicitly). Running
the actual perception pipeline needs torch/onnxruntime/opencv and the
downloaded model weights, none of which are available in this sandbox
(SHARED_BRIEF.md), so `detect()` itself is exercised only through its pure
helper functions here; the full run is marked `xfail`/skipped with a reason.
"""

from __future__ import annotations

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
    detector = F1Detector(settings, knowledge.enabled_rules())
    assert "L-NO-CASH-ON-LEAVE" in detector._rules_by_id
    # Not canonical (see knowledge/rules.yaml); must be dropped by the detector.
    assert "L-NO-BAG-ON-LEAVE" not in detector._rules_by_id
    assert "K-COLLECTOR-DOC" not in detector._rules_by_id


def _detector(tmp_path, rules=None) -> F1Detector:
    rules = rules if rules is not None else [make_rule(rid) for rid in ("L-PC-LOCKED",)]
    return F1Detector(Settings(api_key="k", work_dir=tmp_path), rules)


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
