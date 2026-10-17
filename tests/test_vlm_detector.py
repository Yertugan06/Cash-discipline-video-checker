"""End-to-end tests for VlmDetector: sampler + client + the WP3 rules seam.

`backend.media.extract_jpeg` is injected as a test double (`frame_source`):
SHARED_BRIEF.md notes there is no ffmpeg on this machine, so the real
extractor cannot run here. `backend.rules.evaluate` is injected as a test
double in most tests (SHARED_BRIEF.md: WP2's tests may use a test double for
WP3's rules function), but `test_detector_runs_through_the_real_rules_module`
below calls WP3's actual module, now that it exists in this tree. The vLLM
server is always a mocked httpx transport, never a real network call.
"""

import json
import time
from pathlib import Path

import httpx
import pytest

from backend.contracts import RuleEntry, SamplingPlan, StateTimeline, VideoInfo
from backend.vlm.config import VlmSettings
from backend.vlm.detector import VlmDetector
from backend.vlm.errors import TooManyFailedFramesError, VlmUnavailableError

FIXTURE_IMAGE = (Path(__file__).parent / "fixtures" / "vlm" / "frame.jpg").read_bytes()

VALID_STATE = {
    "cashier_at_desk": True,
    "cashier_in_room": True,
    "people_cashier_side": 1,
    "clients_at_desk": 0,
    "person_at_door": False,
    "collector_present": False,
    "desk_cash": False,
    "desk_bag": False,
    "desk_documents": False,
    "desk_personal_items": False,
    "desk_food_drink": False,
    "phone_in_cashier_hand": False,
    "id_document_visible": False,
    "counting_machine_in_use": False,
    "detector_in_use": False,
    "safe_door": "closed",
    "key_in_safe_lock": "no",
    "laptop_screen": "unlocked",
    "room_door": "closed",
    "cash_in_hands_of": "nobody",
    "cashier_action": "working_on_laptop",
}


def _video_info(duration: float = 16.0) -> VideoInfo:
    return VideoInfo(sha256="b" * 64, duration_sec=duration, width=640, height=480, fps=25.0)


def _plan(deadline_monotonic: float, coarse_t=None, fill_t=None) -> SamplingPlan:
    return SamplingPlan(
        coarse_t=coarse_t if coarse_t is not None else [0.0, 4.0, 8.0, 12.0, 16.0],
        fill_t=fill_t if fill_t is not None else [2.0, 6.0, 10.0, 14.0],
        deadline_monotonic=deadline_monotonic,
    )


def _settings(**overrides) -> VlmSettings:
    return VlmSettings(model="test-model", **overrides)


def _no_rules_evaluate(calls: list | None = None):
    def evaluate(timeline: StateTimeline, rules: list[RuleEntry]) -> list:
        if calls is not None:
            calls.append(timeline)
        return []

    return evaluate


def _frame_source():
    def extract(video: Path, t: float, max_side: int | None) -> bytes:
        return FIXTURE_IMAGE

    return extract


def _detector(
    client: httpx.Client, settings: VlmSettings, calls: list | None = None
) -> VlmDetector:
    return VlmDetector(
        settings,
        rules=[],
        frame_source=_frame_source(),
        rules_evaluate=_no_rules_evaluate(calls),
        http_client=client,
    )


def _valid_response() -> httpx.Response:
    content = json.dumps(VALID_STATE)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _far_deadline() -> float:
    return time.monotonic() + 1000


def test_valid_answers_give_full_coverage_and_calls_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _valid_response()

    seen_timelines: list[StateTimeline] = []
    settings = _settings()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.base_url)
    detector = _detector(client, settings, calls=seen_timelines)

    plan = _plan(deadline_monotonic=_far_deadline())
    result = detector.detect(Path("video.mov"), _video_info(), plan)
    detector.close()

    assert result.coverage.mode == "full"
    assert result.coverage.failed == 0
    assert result.coverage.done == result.coverage.planned
    assert result.warnings == []
    assert len(seen_timelines) == 1
    assert all(o.ok for o in seen_timelines[0].frames)


def test_too_many_failed_frames_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    settings = _settings(max_failed_frac=0.30)
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.base_url)
    detector = _detector(client, settings)

    plan = _plan(deadline_monotonic=_far_deadline())
    with pytest.raises(TooManyFailedFramesError):
        detector.detect(Path("video.mov"), _video_info(), plan)
    detector.close()


def test_unreachable_server_raises_vlm_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    settings = _settings()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.base_url)
    detector = _detector(client, settings)

    plan = _plan(deadline_monotonic=_far_deadline())
    with pytest.raises(VlmUnavailableError):
        detector.detect(Path("video.mov"), _video_info(), plan)
    detector.close()


def test_short_deadline_returns_partial_or_coarse_before_deadline() -> None:
    """A slow fake server plus a tight real deadline must still return promptly."""

    def handler(request: httpx.Request) -> httpx.Response:
        time.sleep(0.05)  # simulate a slow VLM
        return _valid_response()

    settings = _settings(max_in_flight=1, stop_margin_s=0.0, request_timeout_s=5.0)
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=settings.base_url)
    detector = _detector(client, settings)

    coarse_t = [float(i) for i in range(20)]  # far more than the deadline allows at 0.05 s/frame
    plan = _plan(deadline_monotonic=time.monotonic() + 0.12, coarse_t=coarse_t, fill_t=[])

    started = time.monotonic()
    result = detector.detect(Path("video.mov"), _video_info(duration=20.0), plan)
    elapsed = time.monotonic() - started
    detector.close()

    assert elapsed < 1.0  # returned promptly, not after processing all 20 frames
    assert result.coverage.mode in ("partial", "coarse")
    assert result.coverage.deadline_hit is True
    assert result.coverage.done < result.coverage.planned
    assert result.warnings, "a coarse/partial result must carry a human-readable warning"


def test_detector_runs_through_the_real_rules_module() -> None:
    """One pass through WP3's real `backend.rules.evaluate`, not a test double.

    Every mocked frame reports the same steady state (cashier at the desk
    throughout), so no "cashier left the desk" event exists in the timeline
    and the rule correctly finds nothing -- this only proves the seam wires
    up end to end, not any particular rule's logic (that is WP3's own
    equivalence tests).
    """
    from backend.rules import evaluate as real_evaluate

    rule = RuleEntry(
        rule_id="L-NO-CASH-ON-LEAVE",
        title_ru="Деньги оставлены без присмотра",
        title_en="Cash left unattended",
        mechanism="cashier leaves the desk while cash is visible on it",
        states_used=["cashier_at_desk", "desk_cash", "desk_bag"],
        params={
            "min_away_s": 1.0,
            "min_samples": 1,
            "check_window_s": 5.0,
            "cash_frac_threshold": 0.5,
        },
        description_template=(
            "с {t_start} по {t_end} с кассир вне рабочего места; на столе {object}"
        ),
        visibility_caveat="camera cannot confirm who, if anyone, is near the cash",
        norm_ids=["placeholder-norm"],
        enabled=True,
    )

    settings = _settings()
    transport = httpx.MockTransport(lambda r: _valid_response())
    client = httpx.Client(transport=transport, base_url=settings.base_url)
    detector = VlmDetector(
        settings,
        rules=[rule],
        frame_source=_frame_source(),
        rules_evaluate=real_evaluate,
        http_client=client,
    )

    plan = _plan(deadline_monotonic=_far_deadline())
    result = detector.detect(Path("video.mov"), _video_info(), plan)
    detector.close()

    assert result.findings == []
    assert result.coverage.mode == "full"
