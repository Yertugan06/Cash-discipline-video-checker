"""CPU contract/failure tests. Fake inference does not validate a visual model."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.f1 import visual_checks as vc
from backend.f1.events import EventLog
from backend.f1.vision_types import Detection, Event, Observation, Scene, State


def object_box(family="door", box=(0.2, 0.1, 0.8, 0.9)):
    return Detection(label=family, score=0.9, box=box)


def observations(duration=10):
    return [
        Observation(
            timestamp_sec=i / 2,
            detections=[],
            states={
                "door": State(value="closed", score=0.8, margin=0.2),
                "laptop": State(value="closed", score=0.8, margin=0.2),
                "safe": State(value="closed", score=0.8, margin=0.2),
            },
        )
        for i in range(duration * 2)
    ]


def log(*events):
    return EventLog(list(events), {}, [], {})


class FakeBackend:
    def __init__(self, raw='{"answer":"open"}'):
        self.raw = raw
        self.calls = []
        self.fingerprint = "test-model-v1"

    def identity(self):
        return {"backend": "test_fake", "files_sha256": self.fingerprint}

    def ask(self, frame, request, deadline):
        self.calls.append((frame, request, deadline))
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw


@pytest.fixture
def inputs(tmp_path):
    video = tmp_path / "synthetic.mov"
    video.write_text("test-video-content")
    frames = []
    for i in range(20):
        path = tmp_path / f"{i:06d}.jpg"
        # The fake backend does not decode these files; they are explicitly not images.
        path.write_text(f"synthetic-frame-{i}")
        frames.append(path)
    return {
        "video": video,
        "scene": Scene(objects={"door": object_box()}),
        "log": log(),
        "observations": observations(),
        "frames": frames,
        "duration": 10,
        "deadline_monotonic": time.monotonic() + 30,
        "options": vc.VisualCheckSettings(
            enabled=True,
            cache_dir=tmp_path / "answers",
            families=vc.FAMILIES,
        ),
    }


def test_disabled_is_a_noop_without_accessing_video_or_backend(inputs):
    inputs["video"] = Path("does-not-exist")
    inputs["options"] = vc.VisualCheckSettings()
    assert vc.verify_video(**inputs, backend=object()) == []


def test_scene_start_is_not_an_entry_and_cutoff_does_not_add_future_samples():
    scene = Scene(objects={f: object_box(f) for f in vc.FAMILIES})
    events = log(
        Event(type="ENTER", timestamp_sec=0, facts={"observed_entry": True}),
        Event(type="ENTER", timestamp_sec=2, facts={"observed_entry": False}),
        Event(type="ENTER", timestamp_sec=9, facts={"observed_entry": True}),
    )
    requests = vc.plan_checks(scene, events, observations(), 10)
    assert len(requests) == 6
    assert all(r.trigger == "scene_start" and r.observed_entry is False for r in requests)
    assert all(r.t < 10 for r in requests)


def test_observed_entry_and_leave_plan_use_calibrated_boxes():
    scene = Scene(objects={f: object_box(f) for f in vc.FAMILIES})
    events = log(
        Event(type="ENTER", timestamp_sec=2, facts={"observed_entry": True, "actor_id": "p2"}),
        Event(type="EXIT", timestamp_sec=8, facts={"role": "cashier", "actor_id": "p1"}),
    )
    requests = vc.plan_checks(scene, events, observations(), 10)
    assert [(r.family, r.t) for r in requests if r.trigger == "observed_entry"] == [
        ("door", 6),
        ("door", 6.5),
        ("door", 7),
    ]
    assert {(r.family, r.t) for r in requests if r.trigger == "exit"} == {
        (f, t) for f in ("laptop", "safe") for t in (8, 8.5, 9)
    }
    assert all(r.box == scene.objects[r.family].box for r in requests)


def test_planner_does_not_bridge_an_occluded_perception_interval():
    sparse = [Observation(timestamp_sec=t, detections=[]) for t in (0, 9)]
    requests = vc.plan_checks(Scene(objects={}), log(), sparse, 10)
    assert len(requests) == 2
    assert {r.t for r in requests} == {0}


def test_safe_departure_is_selected_even_with_no_safe_open_event():
    scene = Scene(objects={"safe": object_box("safe", (0.0, 0.1, 0.2, 0.9))})
    frames = observations()
    for i, frame in enumerate(frames):
        frame.detections = [
            Detection(
                label="person",
                score=0.9,
                track_id="p1",
                role="cashier",
                box=(0.03, 0.2, 0.17, 0.8) if i < 4 else (0.6, 0.2, 0.8, 0.8),
            )
        ]
    requests = vc.plan_checks(scene, log(), frames, 10)
    assert [(r.t, r.trigger_t) for r in requests if r.trigger == "safe_departure"] == [
        (2, 2),
        (2.5, 2),
        (3, 2),
        (6, 2),
        (6.5, 2),
        (7, 2),
    ]


@pytest.mark.parametrize("box", [(0.8, 0, 0.2, 1), (0, 0, 1.2, 1), (float("nan"), 0, 1, 1)])
def test_bad_calibration_is_unknown_and_does_not_call_model(inputs, box):
    inputs["scene"].objects["door"].box = box
    backend = FakeBackend()
    checks = vc.verify_video(**inputs, backend=backend)
    assert not backend.calls
    assert all(c["answer"] == "unknown" and c["error"] == "missing_calibration" for c in checks)


@pytest.mark.parametrize(
    "raw",
    [
        "open",
        '```json\n{"answer":"open"}\n```',
        '{"answer":"no"}',
        '{"answer":false}',
        '{"answer":"locked"}',
        '{"answer":"open","cash":true}',
        '{"answer":"closed","answer":"open"}',
        "[]",
        "null",
        '{"answer":"OPEN"}',
    ],
)
def test_invalid_model_answers_never_become_a_state(inputs, raw):
    checks = vc.verify_video(**inputs, backend=FakeBackend(raw))
    door = [c for c in checks if c["family"] == "door"]
    assert all(c["answer"] == "unknown" and not c["ok"] for c in door)
    assert all(c["error"] == "invalid_output" for c in door)


def test_valid_occlusion_answer_is_unknown_without_mutating_original_state(inputs):
    checks = vc.verify_video(**inputs, backend=FakeBackend('{"answer":"unknown"}'))
    assert all(c["ok"] for c in checks if c["family"] == "door")
    refined = vc.apply_checks(inputs["observations"], checks)
    assert refined == inputs["observations"]
    assert all(c["answer"] == "unknown" and not c["applied"] for c in checks)


def test_confirmed_state_refines_exact_samples_without_cash_or_confidence(inputs):
    inputs["scene"] = Scene(objects={"safe": object_box("safe")})
    inputs["options"] = inputs["options"].model_copy(update={"families": ("safe",)})
    checks = vc.verify_video(**inputs, backend=FakeBackend())
    original = inputs["observations"]
    refined = vc.apply_checks(original, checks)
    assert [o.states["safe"].value for o in refined[:4]] == ["open", "open", "open", "closed"]
    assert original[0].states["safe"].value == "closed"
    assert refined[0].states["safe"].score == 0
    assert all(not o.detections for o in refined)
    assert all(c["applied"] for c in checks)


def test_laptop_planner_only_checks_room_exit():
    scene = Scene(objects={f: object_box(f) for f in vc.FAMILIES})
    events = log(
        Event(type="WORKSTATION_AWAY_START", timestamp_sec=2, facts={"role": "cashier"}),
        Event(type="EXIT", timestamp_sec=7, facts={"role": "cashier"}),
    )
    requests = vc.plan_checks(scene, events, observations(), 10)
    assert [(r.t, r.trigger) for r in requests if r.family == "laptop"] == [
        (7, "exit"),
        (7.5, "exit"),
        (8, "exit"),
    ]


def test_conflicting_answers_are_unknown_and_safe_lock_state_is_rejected(inputs):
    base = {"family": "door", "t": 0, "box": (0, 0, 1, 1), "ok": True}
    checks = [
        {**base, "answer": "open"},
        {**base, "answer": "closed"},
        {**base, "family": "safe", "answer": "locked"},
    ]
    refined = vc.apply_checks(inputs["observations"], checks)
    assert refined[0].states["door"].value == "unknown"
    assert refined[0].states["safe"].value == "closed"
    assert checks[0]["apply_warning"] == "conflicting_answers"
    assert "lock is locked" in vc.QUESTIONS["safe"][0]


def test_model_unavailable_and_missing_frame_are_explicit(inputs):
    backend = FakeBackend(vc.ModelUnavailable("cuda_unavailable"))
    checks = vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 1
    assert sum(c["inference_requested"] for c in checks) == 1
    assert not any(c["inference_ran"] for c in checks)
    assert all(c["error"] == "cuda_unavailable" for c in checks if c["family"] == "door")
    inputs["frames"] = []
    checks = vc.verify_video(**inputs, backend=FakeBackend())
    assert all(c["error"] == "sample_frame_missing" for c in checks if c["family"] == "door")


def test_unconfigured_local_model_is_unknown_without_loading_torch(inputs):
    checks = vc.verify_video(**inputs)
    assert all(c["answer"] == "unknown" for c in checks)
    assert any(c.get("error") == "local_weights_missing" for c in checks)


def test_finite_check_budget_and_video_deadline(inputs):
    inputs["options"] = inputs["options"].model_copy(update={"max_checks": 1})
    backend = FakeBackend()
    checks = vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 1
    assert sum(c.get("error") == "check_budget_exhausted" for c in checks) == 2
    inputs["deadline_monotonic"] = time.monotonic() - 1
    backend = FakeBackend()
    checks = vc.verify_video(**inputs, backend=backend)
    assert not backend.calls
    assert all(c.get("error") == "video_deadline" for c in checks if c["family"] == "door")


def test_event_checks_precede_bootstrap_with_round_robin_families():
    scene = Scene(objects={f: object_box(f) for f in vc.FAMILIES})
    events = log(Event(type="EXIT", timestamp_sec=8, facts={"role": "cashier"}))
    planned = vc.plan_checks(scene, events, observations(), 10)
    scheduled = vc._schedule_requests(planned)
    assert [(r.family, r.trigger) for r in scheduled[:9:3]] == [
        ("door", "scene_start"),
        ("laptop", "exit"),
        ("safe", "exit"),
    ]


def test_cache_hits_and_invalidates_model_frame_prompt_crop_and_video(inputs, monkeypatch):
    backend = FakeBackend()
    first = vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 3
    second = vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 3
    assert all(c["cache_hit"] for c in second if c["family"] == "door")
    assert {c["cache_key"] for c in first if c["family"] == "door"} == {
        c["cache_key"] for c in second if c["family"] == "door"
    }
    inputs["frames"][0].write_text("changed sampled frame")
    vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 4
    backend.fingerprint = "test-model-v2"
    vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 7
    old = vc.QUESTIONS["door"]
    monkeypatch.setitem(vc.QUESTIONS, "door", (old[0] + " More precise prompt.", old[1]))
    vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 10
    inputs["scene"].objects["door"].box = (0.1, 0.1, 0.9, 0.9)
    vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 13
    inputs["video"].write_text("new video content")
    vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 16


def test_cache_key_covers_sampling_and_generation_settings():
    request = vc.CheckRequest("door", 1, (0, 0, 1, 1), "q1", "scene_start", 0)
    options = vc.VisualCheckSettings()
    original = vc.cache_identity("a" * 64, {}, request, options, 2, "b" * 64)
    assert original != vc.cache_identity("a" * 64, {}, request, options, 1, "b" * 64)
    assert original != vc.cache_identity("a" * 64, {}, replace(request, t=2), options, 2, "b" * 64)
    assert original != vc.cache_identity(
        "a" * 64,
        {},
        request,
        options.model_copy(update={"max_side": 640}),
        2,
        "b" * 64,
    )


def test_corrupt_cache_is_reported_and_not_used(inputs):
    backend = FakeBackend()
    vc.verify_video(**inputs, backend=backend)
    for path in inputs["options"].cache_dir.glob("*.json"):
        path.write_text('{"raw":"false"}')
    checks = vc.verify_video(**inputs, backend=backend)
    assert len(backend.calls) == 6
    assert all(
        c.get("cache_warning") == "invalid_cache_entry" for c in checks if c["family"] == "door"
    )


def test_local_weight_identity_changes_with_config_and_rejects_missing_weights(tmp_path):
    with pytest.raises(vc.ModelUnavailable):
        vc.model_identity(tmp_path)
    (tmp_path / "config.json").write_text('{"model_type":"qwen3_vl"}')
    (tmp_path / "model.safetensors").write_text("synthetic-not-real-weights")
    before = vc.model_identity(tmp_path)
    (tmp_path / "config.json").write_text('{"model_type":"qwen3_vl","changed":true}')
    assert before != vc.model_identity(tmp_path)


def test_parent_kills_a_nonresponsive_local_worker_at_deadline(tmp_path, monkeypatch):
    real_popen = subprocess.Popen

    def spawn_nonresponsive(*args, **kwargs):
        return real_popen(
            [sys.executable, "-u", "-c", "import sys,time; next(sys.stdin); time.sleep(20)"],
            **kwargs,
        )

    monkeypatch.setattr(vc.subprocess, "Popen", spawn_nonresponsive)
    backend = vc.LocalQwenBackend(vc.VisualCheckSettings())
    request = vc.CheckRequest("door", 0, (0, 0, 1, 1), "q1", "scene_start", 0)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        backend.ask(tmp_path / "unused.jpg", request, time.monotonic() + 0.15)
    assert time.monotonic() - started < 2
    assert backend._process is None


def test_explicit_worker_python_controls_launch_and_runtime_identity(tmp_path, monkeypatch):
    python = tmp_path / "working-ml-python"
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "model.safetensors").write_text("synthetic-not-real-weights")
    runtime = {"worker_python": str(python), "transformers": "5.20.1", "accelerate": "1.15.0"}
    inspected = []

    def environment(path):
        inspected.append(path)
        return runtime

    monkeypatch.setattr(vc, "worker_environment", environment)
    backend = vc.LocalQwenBackend(vc.VisualCheckSettings(model_path=model, worker_python=python))
    assert backend.identity()["transformers"] == "5.20.1"
    assert inspected == [str(python)]
    real_popen = subprocess.Popen

    def spawn(command, **kwargs):
        assert command[0] == str(python)
        return real_popen(
            [
                sys.executable,
                "-u",
                "-c",
                "import sys,json; next(sys.stdin); "
                "print('A21_VISUAL_RESULT '+"
                "json.dumps({'raw':'{\"answer\":\"unknown\"}'}),flush=True)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(vc.subprocess, "Popen", spawn)
    try:
        request = vc.CheckRequest("door", 0, (0, 0, 1, 1), "q1", "scene_start", 0)
        assert (
            backend.ask(tmp_path / "unused.jpg", request, time.monotonic() + 5)
            == '{"answer":"unknown"}'
        )
    finally:
        backend.close()


def test_observed_device_map_valueerror_keeps_sanitized_load_diagnostics(monkeypatch, capsys):
    def fail_load(*args, **kwargs):
        raise ValueError("Using a device_map requires accelerate. API_KEY=private-test-secret")

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: True),
            set_num_threads=lambda _: None,
            bfloat16="test-dtype",
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoProcessor=object(),
            Qwen3VLForConditionalGeneration=SimpleNamespace(from_pretrained=fail_load),
        ),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "options": vc.VisualCheckSettings().model_dump(mode="json"),
                    "deadline": time.monotonic() + 5,
                    "lock_held": True,
                }
            )
            + "\n"
        ),
    )
    vc._worker_main()
    response = json.loads(capsys.readouterr().out.removeprefix("A21_VISUAL_RESULT "))
    assert response["error"] == "local_inference_failed:ValueError"
    assert response["diagnostic"]["stage"] == "model_load"
    assert "requires accelerate" in response["diagnostic"]["message"]
    assert "private-test-secret" not in response["diagnostic"]["message"]
    assert response["diagnostic"]["frames"]


def test_model_failure_details_are_private_and_do_not_claim_inference(inputs):
    diagnostic = {"stage": "model_load", "message": "Using a device_map requires accelerate"}
    backend = FakeBackend(
        vc.ModelUnavailable("local_inference_failed:ValueError", diagnostic=diagnostic)
    )
    checks = vc.verify_video(**inputs, backend=backend)
    first = next(check for check in checks if check.get("diagnostic_file"))
    path = Path(first["diagnostic_file"])
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["diagnostic"] == diagnostic
    assert not any(c["inference_ran"] for c in checks)
    assert not any("diagnostic" in c for c in checks)


@pytest.mark.parametrize(
    "update",
    [
        {"max_checks": -1},
        {"max_video_s": float("nan")},
        {"request_timeout_s": 0},
        {"crop_margin": 2},
        {"max_new_tokens": 1000},
        {"enabled": "nonsense"},
        {"families": ("cash",)},
    ],
)
def test_settings_validate_external_inputs(update):
    with pytest.raises(ValidationError):
        vc.VisualCheckSettings(**update)


def test_settings_environment_is_opt_in_and_import_stays_light(monkeypatch):
    from backend.config import Settings

    monkeypatch.setenv("API_KEY", "test-only")
    monkeypatch.delenv("F1_VISUAL_CHECKS", raising=False)
    assert Settings.from_env().visual_checks.enabled is False
    monkeypatch.setenv("F1_VISUAL_CHECKS", "1")
    monkeypatch.setenv("F1_VISUAL_MAX_CHECKS", "6")
    assert Settings.from_env().visual_checks.max_checks == 6
    code = (
        "import sys,json; import backend.f1.visual_checks; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'torch','transformers','PIL','cv2','onnxruntime'})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == []
    # backend.media already imports PIL in the existing application. The new
    # verifier must keep the established no-torch/model-import guarantee.
    result = subprocess.run(
        [sys.executable, "-c", code.replace("backend.f1.visual_checks", "backend.main")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["PIL"]
