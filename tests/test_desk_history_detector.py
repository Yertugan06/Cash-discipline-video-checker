"""A18 stays opt-in and uses the detector's already decoded frames and job deadline."""

import json
import time

import numpy as np
import pytest
import yaml

from backend.config import ROOT, Settings
from backend.contracts import SamplingPlan, VideoInfo
from backend.f1.detector import F1Detector, F1DetectorError, _desk_images
from backend.f1.events import EventLog
from backend.f1.perception import load_perception_config
from backend.f1.vision_types import Detection, Event, Observation, Scene
from backend.knowledge import Knowledge
from tests.conftest import make_rule


def perception_file(tmp_path, **settings):
    config = yaml.safe_load((ROOT / "config/perception.yaml").read_text())
    config.update(settings)
    path = tmp_path / "perception.yaml"
    path.write_text(yaml.safe_dump(config))
    return path


@pytest.mark.parametrize("enabled", [False, True])
def test_desk_history_config_accepts_only_explicit_boolean_values(tmp_path, enabled):
    path = perception_file(tmp_path, desk_objects=enabled)
    assert load_perception_config(path)["desk_objects"] is enabled


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_desk_history_config_rejects_ambiguous_values(tmp_path, value):
    path = perception_file(tmp_path, desk_objects=value)
    with pytest.raises(ValueError, match="desk_objects"):
        load_perception_config(path)


def test_older_perception_configs_default_to_history_disabled(tmp_path):
    path = perception_file(tmp_path)
    config = yaml.safe_load(path.read_text())
    config.pop("desk_objects", None)
    path.write_text(yaml.safe_dump(config))
    assert load_perception_config(path)["desk_objects"] is False
    assert load_perception_config(ROOT / "config/perception.yaml")["desk_objects"] is False


@pytest.fixture
def desk_clip(tmp_path, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    from backend.f1 import detector as detector_module
    from backend.f1 import events, perception

    desk = (0.2, 0.3, 0.8, 0.8)
    item = (0.45, 0.5, 0.55, 0.6)
    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=desk),
            "safe": Detection(label="safe", score=1, box=(0.85, 0.1, 0.98, 0.4)),
        },
        zones={
            "desk": [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)],
            "safe": [(0.85, 0.1), (0.98, 0.1), (0.98, 0.4), (0.85, 0.4)],
        },
        confidence=1,
    )
    observations = []
    for index in range(16):
        detections = []
        if index >= 4:
            detections.append(Detection(label="cash", score=0.9, box=item, track_id="cash:1"))
        if index in (1, 3):
            hand = (0.9, 0.2) if index == 1 else (0.5, 0.55)
            detections.append(
                Detection(
                    label="person",
                    score=1,
                    box=(0, 0, 0.1, 0.1),
                    track_id="person:1",
                    hands=[(*hand, 1)],
                )
            )
        observations.append(Observation(timestamp_sec=index * 0.5, detections=detections))

    def extract_frames(video, frames_dir, deadline):
        frames = []
        for index in range(16):
            image = np.full((200, 300, 3), 120, dtype=np.uint8)
            if index >= 4:
                image[100:120, 135:165] = 40
            path = frames_dir / f"{index:06d}.jpg"
            assert cv2.imwrite(str(path), image)
            frames.append(path)
        return frames

    config = load_perception_config(ROOT / "config/perception.yaml")
    monkeypatch.setattr(F1Detector, "_extract_frames", staticmethod(extract_frames))
    monkeypatch.setattr(perception, "perceive_video", lambda *args: (scene, observations, config))
    log = EventLog(
        [
            Event(type="SAFE_OPEN", timestamp_sec=0, facts={"state": "open"}),
            Event(type="EXIT", timestamp_sec=3, facts={"actor_id": "person:1", "role": "cashier"}),
        ],
        {"roles": True, "desk": True},
        [],
        {},
    )
    monkeypatch.setattr(events, "build_events", lambda *args: log)
    video = tmp_path / "clip.mov"
    video.write_bytes(b"perception is supplied by the test")
    rules = {rule.rule_id: rule for rule in Knowledge.load(ROOT / "knowledge").rules}
    rules["L-NO-CASH-ON-LEAVE"] = make_rule("L-NO-CASH-ON-LEAVE")
    detector = F1Detector(Settings(api_key="test", work_dir=tmp_path), list(rules.values()))
    info = VideoInfo(sha256="ab" * 32, duration_sec=8, width=300, height=200, fps=2)
    plan = SamplingPlan(coarse_t=[], fill_t=[], deadline_monotonic=time.monotonic() + 60)
    return detector_module, detector, video, info, plan, config, observations, scene


@pytest.mark.parametrize("enabled", [False, True])
def test_detector_runs_leave_rules_with_the_selected_item_source(desk_clip, enabled):
    _, detector, video, info, plan, config, _, _ = desk_clip
    config["desk_objects"] = enabled
    result = detector.detect(video, info, plan)
    assert [f.rule_id for f in result.findings] == ["L-NO-CASH-ON-LEAVE"]
    finding = result.findings[0]
    trace = json.loads((detector._settings.traces_dir / "clip.json").read_text())
    assert trace["desk_objects_enabled"] is enabled
    if enabled:
        assert finding.facts["track_ids"] == "cash:desk1"
        assert finding.facts["clues"] == "detector:cash,origin:safe"
        assert finding.boxes[0].box == pytest.approx((0.45, 0.5, 0.55, 0.6), abs=0.02)
        assert trace["desk_objects"][0]["origin"] == "safe"
        assert trace["desk_objects"][0]["seen"][0] == 2
    else:
        assert finding.facts["track_ids"] == "cash:1"
        assert trace["desk_objects"] is None
    assert result.coverage.done == 16
    assert not list(video.parent.glob("f1-frames-*"))


def test_disabled_history_does_not_read_frames_again(desk_clip, monkeypatch):
    module, detector, video, info, plan, _, _, _ = desk_clip

    def unexpected_history(*args):
        pytest.fail("Desk history must stay disabled by default")

    monkeypatch.setattr(module, "_desk_images", unexpected_history)
    assert detector.detect(video, info, plan).findings


def test_enabled_history_rejects_misaligned_cached_observations(desk_clip):
    _, detector, video, info, plan, config, observations, _ = desk_clip
    config["desk_objects"] = True
    observations.pop()
    with pytest.raises(F1DetectorError, match="do not match"):
        detector.detect(video, info, plan)
    assert not list(video.parent.glob("f1-frames-*"))


def test_enabled_history_cleans_up_frames_when_image_decoding_fails(desk_clip, monkeypatch):
    import cv2

    _, detector, video, info, plan, config, _, _ = desk_clip
    config["desk_objects"] = True
    monkeypatch.setattr(cv2, "imread", lambda *args: None)
    with pytest.raises(F1DetectorError, match="could not be decoded"):
        detector.detect(video, info, plan)
    assert not list(video.parent.glob("f1-frames-*"))


def test_desk_images_rejects_an_unreadable_frame(tmp_path):
    pytest.importorskip("cv2")
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not an image")
    with pytest.raises(F1DetectorError, match="could not be decoded"):
        list(_desk_images([path], time.monotonic() + 60))


def test_desk_images_stops_when_the_job_budget_is_spent(tmp_path):
    pytest.importorskip("cv2")
    with pytest.raises(F1DetectorError, match="time limit"):
        list(_desk_images([tmp_path / "frame.jpg"], time.monotonic() - 1))
