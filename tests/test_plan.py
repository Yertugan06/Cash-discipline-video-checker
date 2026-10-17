"""Pure tests for `backend.plan.build_plan` (no ffmpeg needed)."""

from __future__ import annotations

import pytest

from backend.contracts import VideoInfo
from backend.plan import build_plan


def info(duration: float) -> VideoInfo:
    return VideoInfo(sha256="0" * 64, duration_sec=duration, width=640, height=480, fps=25.0)


def test_coarse_grid_is_a_4s_grid_plus_a_point_near_the_end():
    plan = build_plan(info(18.0), deadline_monotonic=1000.0)
    assert plan.coarse_t[:5] == [0.0, 4.0, 8.0, 12.0, 16.0]
    assert plan.coarse_t[-1] > 16.0
    assert plan.coarse_t[-1] < 18.0
    assert plan.coarse_t == sorted(set(plan.coarse_t))


def test_fill_times_are_midpoints_and_never_duplicate_a_coarse_time():
    plan = build_plan(info(18.0), deadline_monotonic=1000.0)
    for a, b in zip(plan.coarse_t, plan.coarse_t[1:], strict=False):
        midpoint = round((a + b) / 2, 3)
        assert midpoint in plan.fill_t
    assert set(plan.fill_t).isdisjoint(plan.coarse_t)
    assert len(plan.fill_t) == len(plan.coarse_t) - 1


def test_deadline_is_passed_through_unchanged():
    plan = build_plan(info(10.0), deadline_monotonic=12345.0)
    assert plan.deadline_monotonic == 12345.0


def test_short_video_still_gets_a_coarse_and_fill_point():
    plan = build_plan(info(1.0), deadline_monotonic=1.0)
    assert plan.coarse_t[0] == 0.0
    assert len(plan.coarse_t) >= 2
    assert len(plan.fill_t) >= 1
    assert all(0.0 <= t <= 1.0 for t in plan.coarse_t + plan.fill_t)


def test_custom_steps_change_the_grid_spacing():
    plan = build_plan(info(20.0), deadline_monotonic=0.0, coarse_step_s=5.0, fill_step_s=2.5)
    assert plan.coarse_t[:4] == [0.0, 5.0, 10.0, 15.0]


@pytest.mark.parametrize("coarse_step_s,fill_step_s", [(0, 2.0), (4.0, 0), (-1.0, 2.0)])
def test_non_positive_steps_are_rejected(coarse_step_s, fill_step_s):
    with pytest.raises(ValueError):
        build_plan(
            info(10.0), deadline_monotonic=0.0, coarse_step_s=coarse_step_s, fill_step_s=fill_step_s
        )
