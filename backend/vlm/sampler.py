"""Coarse-first, deadline-aware frame scheduler (architecture.md §4).

Issues `plan.coarse_t` first, then `plan.fill_t` only while the running mean
seconds-per-frame estimate says the next request still fits before
`plan.deadline_monotonic - settings.stop_margin_s`. Runs up to
`settings.max_in_flight` requests concurrently (plain threads: the per-frame
work is a blocking HTTP call plus a blocking frame extraction, so threads are
simpler than asyncio here and good enough at this concurrency). Returns a
`StateTimeline` built from whatever completed before the cutoff; never blocks
past the deadline to finish the whole plan.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from backend.contracts import Coverage, FrameObservation, SamplingPlan, StateTimeline, VideoInfo
from backend.vlm.config import VlmSettings

Clock = Callable[[], float]
AskFrame = Callable[[float], FrameObservation]

# Only used when `plan.coarse_t` has fewer than two points (a very short
# video), so `Coverage.step_s` still has a sensible value to report.
_DEFAULT_COARSE_STEP_S = 4.0


def run_sampler(
    video_info: VideoInfo,
    plan: SamplingPlan,
    ask_frame: AskFrame,
    settings: VlmSettings,
    clock: Clock = time.monotonic,
) -> StateTimeline:
    """Runs the coarse-then-fill plan and returns the resulting `StateTimeline`.

    `ask_frame(t)` must do the frame extraction and the VLM call and return a
    `FrameObservation`; letting any `VlmError` it raises (e.g.
    `VlmUnavailableError`) propagate unchanged.
    """
    stop_at = plan.deadline_monotonic - settings.stop_margin_s

    coarse_done, coarse_cut = _run_phase(
        plan.coarse_t, ask_frame, settings.max_in_flight, stop_at, clock
    )
    fill_done: list[FrameObservation] = []
    fill_cut = False
    if not coarse_cut:
        fill_done, fill_cut = _run_phase(
            plan.fill_t, ask_frame, settings.max_in_flight, stop_at, clock
        )

    observations = coarse_done + fill_done
    observations.sort(key=lambda o: o.t)

    planned = len(plan.coarse_t) + len(plan.fill_t)
    done = len(observations)
    failed = sum(1 for o in observations if not o.ok)
    deadline_hit = coarse_cut or fill_cut

    if coarse_cut:
        mode = "partial"
    elif fill_cut:
        mode = "coarse"
    else:
        mode = "full"

    step_s = settings.fill_step_s if mode == "full" else _coarse_step(plan.coarse_t)

    coverage = Coverage(
        step_s=step_s,
        planned=planned,
        done=done,
        failed=failed,
        deadline_hit=deadline_hit,
        mode=mode,
    )
    return StateTimeline(video=video_info, frames=observations, coverage=coverage)


def _coarse_step(coarse_t: list[float]) -> float:
    if len(coarse_t) >= 2:
        return coarse_t[1] - coarse_t[0]
    return _DEFAULT_COARSE_STEP_S


def _run_phase(
    times: list[float],
    ask_frame: AskFrame,
    max_in_flight: int,
    stop_at: float,
    clock: Clock,
) -> tuple[list[FrameObservation], bool]:
    """Runs `ask_frame` over `times`, up to `max_in_flight` requests in flight.

    Stops *issuing* new requests once the clock (or the running mean latency
    projected forward) says the next one would not complete before `stop_at`;
    already in-flight requests are left to finish. Returns
    `(observations, cut)`, where `cut` is True iff not every item in `times`
    was issued.
    """
    if not times:
        return [], False

    pending = list(times)
    observations: list[FrameObservation] = []
    latencies: list[float] = []

    def fits_before_deadline() -> bool:
        if clock() >= stop_at:
            return False
        if not latencies:
            return True
        mean_latency = sum(latencies) / len(latencies)
        return clock() + mean_latency <= stop_at

    with ThreadPoolExecutor(max_workers=max_in_flight) as pool:
        futures: dict[Future[FrameObservation], float] = {}

        def fill_pool() -> None:
            while pending and len(futures) < max_in_flight and fits_before_deadline():
                t = pending.pop(0)
                futures[pool.submit(ask_frame, t)] = t

        fill_pool()
        while futures:
            done_futures, _ = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done_futures:
                futures.pop(fut)
                observations.append(fut.result())
                latencies.append(observations[-1].latency_s)
            fill_pool()

    cut = bool(pending)
    return observations, cut
