"""Deadline-aware sampling plan: a coarse 4 s grid, then 2 s fill midpoints.

Pure function; no I/O, no clock reads beyond what the caller passes in.
`architecture.md` §4: the coarse grid covers the whole video early, then the
fill points (one per consecutive coarse pair, at the midpoint) are processed
only while the remaining budget allows.
"""

from __future__ import annotations

from backend.contracts import SamplingPlan, VideoInfo

_EPS = 1e-6


def build_plan(
    info: VideoInfo,
    deadline_monotonic: float,
    coarse_step_s: float = 4.0,
    fill_step_s: float = 2.0,
) -> SamplingPlan:
    """Build the coarse-then-fill sampling plan for one video.

    `coarse_t` is the 0, coarse_step_s, 2*coarse_step_s, ... grid over
    [0, duration), plus one point for the last second of the video.
    `fill_t` is the midpoint of each pair of consecutive coarse times,
    skipping any midpoint that would duplicate a coarse time.
    """
    if coarse_step_s <= 0 or fill_step_s <= 0:
        raise ValueError("coarse_step_s and fill_step_s must be positive")
    duration = info.duration_sec

    coarse: list[float] = []
    t = 0.0
    while t < duration:
        coarse.append(round(t, 3))
        t += coarse_step_s

    last_t = round(max(0.0, duration - min(0.1, duration / 10)), 3)
    if not coarse or abs(coarse[-1] - last_t) > _EPS:
        coarse.append(last_t)
    coarse = sorted(set(coarse))

    fill: list[float] = []
    for a, b in zip(coarse, coarse[1:], strict=False):
        midpoint = round((a + b) / 2, 3)
        if all(abs(midpoint - c) > _EPS for c in coarse):
            fill.append(midpoint)

    return SamplingPlan(coarse_t=coarse, fill_t=fill, deadline_monotonic=deadline_monotonic)
