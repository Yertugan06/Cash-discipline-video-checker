"""Unit tests for backend.vlm.sampler: coarse-first, deadline-aware scheduling.

A `FakeClock` stands in for `time.monotonic`: each fake frame request
advances it by a fixed amount instead of actually sleeping, so the
coarse/fill cutoff logic can be tested deterministically and fast.
"""

import threading

from backend.contracts import FrameObservation, FrameState, SamplingPlan, VideoInfo
from backend.vlm.config import VlmSettings
from backend.vlm.sampler import run_sampler

VALID_STATE = FrameState(
    cashier_at_desk=True,
    cashier_in_room=True,
    people_cashier_side=1,
    clients_at_desk=0,
    person_at_door=False,
    collector_present=False,
    desk_cash=False,
    desk_bag=False,
    desk_documents=False,
    desk_personal_items=False,
    desk_food_drink=False,
    phone_in_cashier_hand=False,
    id_document_visible=False,
    counting_machine_in_use=False,
    detector_in_use=False,
    safe_door="closed",
    key_in_safe_lock="no",
    laptop_screen="unlocked",
    room_door="closed",
    cash_in_hands_of="nobody",
    cashier_action="working_on_laptop",
)


class FakeClock:
    """A monotonic-like clock, advanced manually by fake requests."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._t

    def advance(self, dt: float) -> float:
        with self._lock:
            self._t += dt
            return self._t


def _video_info(duration: float = 16.0) -> VideoInfo:
    return VideoInfo(sha256="a" * 64, duration_sec=duration, width=640, height=480, fps=25.0)


def _plan(deadline_monotonic: float) -> SamplingPlan:
    return SamplingPlan(
        coarse_t=[0.0, 4.0, 8.0, 12.0, 16.0],
        fill_t=[2.0, 6.0, 10.0, 14.0],
        deadline_monotonic=deadline_monotonic,
    )


def _settings(**overrides) -> VlmSettings:
    return VlmSettings(model="test-model", max_in_flight=1, stop_margin_s=0.0, **overrides)


def _ok_ask_frame(clock: FakeClock, cost_s: float = 3.0):
    def ask_frame(t: float) -> FrameObservation:
        clock.advance(cost_s)
        return FrameObservation(t=t, ok=True, state=VALID_STATE, error=None, latency_s=cost_s)

    return ask_frame


def test_full_mode_when_everything_fits() -> None:
    clock = FakeClock()
    plan = _plan(deadline_monotonic=1000.0)  # plenty of budget
    timeline = run_sampler(_video_info(), plan, _ok_ask_frame(clock), _settings(), clock=clock)

    assert timeline.coverage.mode == "full"
    assert timeline.coverage.planned == 9
    assert timeline.coverage.done == 9
    assert timeline.coverage.failed == 0
    assert timeline.coverage.deadline_hit is False
    assert [o.t for o in timeline.frames] == sorted(o.t for o in timeline.frames)
    assert all(o.ok for o in timeline.frames)


def test_partial_mode_when_coarse_itself_is_cut() -> None:
    clock = FakeClock()
    plan = _plan(deadline_monotonic=10.0)  # budget runs out mid coarse grid
    timeline = run_sampler(_video_info(), plan, _ok_ask_frame(clock), _settings(), clock=clock)

    assert timeline.coverage.mode == "partial"
    assert timeline.coverage.deadline_hit is True
    assert timeline.coverage.done < timeline.coverage.planned
    assert timeline.coverage.done < len(plan.coarse_t)


def test_coarse_mode_when_only_fill_is_cut() -> None:
    clock = FakeClock()
    plan = _plan(deadline_monotonic=15.0)  # exactly enough for the 5-point coarse grid
    timeline = run_sampler(_video_info(), plan, _ok_ask_frame(clock), _settings(), clock=clock)

    assert timeline.coverage.mode == "coarse"
    assert timeline.coverage.deadline_hit is True
    assert timeline.coverage.done == len(plan.coarse_t)
    assert timeline.coverage.done < timeline.coverage.planned


def test_failed_frames_are_counted_in_coverage() -> None:
    clock = FakeClock()
    plan = _plan(deadline_monotonic=1000.0)

    def ask_frame(t: float) -> FrameObservation:
        clock.advance(1.0)
        ok = t != 4.0
        return FrameObservation(
            t=t,
            ok=ok,
            state=VALID_STATE if ok else None,
            error=None if ok else "schema validation failed",
            latency_s=1.0,
        )

    timeline = run_sampler(_video_info(), plan, ask_frame, _settings(), clock=clock)

    assert timeline.coverage.mode == "full"
    assert timeline.coverage.failed == 1
    assert timeline.coverage.done == 9
