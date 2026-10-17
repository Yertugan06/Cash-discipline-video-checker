"""`VlmDetector`: whole-video `StateTimeline` via vLLM, then WP3's rules.

Implements the `backend.contracts.Detector` protocol (architecture.md §1-§2,
§4). `backend.media.extract_jpeg` (WP1) and `backend.rules.evaluate` (WP3)
are imported lazily, inside `__init__`'s defaults, so this module can be
imported and unit-tested before those modules exist; both can be overridden
for tests via `frame_source` / `rules_evaluate`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from backend.contracts import (
    Coverage,
    DetectionResult,
    Finding,
    FrameObservation,
    RuleEntry,
    SamplingPlan,
    StateTimeline,
    VideoInfo,
)
from backend.vlm import client as vlm_client
from backend.vlm.config import VlmSettings
from backend.vlm.errors import TooManyFailedFramesError
from backend.vlm.sampler import run_sampler

FrameSource = Callable[[Path, float, int | None], bytes]
Clock = Callable[[], float]
RulesEvaluate = Callable[[StateTimeline, list[RuleEntry]], list[Finding]]

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SCHEMA_PATH = Path(__file__).parent / "form_schema.json"


def _default_frame_source() -> FrameSource:
    from backend.media import extract_jpeg  # WP1, imported lazily; see module docstring

    return extract_jpeg


def _default_rules_evaluate() -> RulesEvaluate:
    from backend.rules import evaluate  # WP3, imported lazily; see module docstring

    return evaluate


class VlmDetector:
    """`Detector.detect` backed by a questionnaire VLM served through vLLM."""

    def __init__(
        self,
        settings: VlmSettings,
        rules: list[RuleEntry],
        *,
        frame_source: FrameSource | None = None,
        rules_evaluate: RulesEvaluate | None = None,
        http_client: httpx.Client | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        self._settings = settings
        self._rules = rules
        self._frame_source = frame_source or _default_frame_source()
        self._rules_evaluate = rules_evaluate or _default_rules_evaluate()
        self._clock = clock
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(
            base_url=settings.base_url, timeout=settings.request_timeout_s
        )
        self._system_prompt = (_PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")
        self._questionnaire_prompt = (_PROMPTS_DIR / "questionnaire.txt").read_text(
            encoding="utf-8"
        )
        self._schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    def detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult:
        def ask_frame(t: float) -> FrameObservation:
            image_bytes = self._frame_source(video, t, self._settings.max_side)
            return vlm_client.ask_frame(
                self._http_client,
                self._settings,
                t,
                image_bytes,
                self._schema,
                self._system_prompt,
                self._questionnaire_prompt,
            )

        timeline = run_sampler(info, plan, ask_frame, self._settings, clock=self._clock)
        _check_failed_fraction(timeline, self._settings.max_failed_frac)

        findings = self._rules_evaluate(timeline, self._rules)
        warnings = _coverage_warnings(timeline.coverage)
        return DetectionResult(findings=findings, coverage=timeline.coverage, warnings=warnings)

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> VlmDetector:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _check_failed_fraction(timeline: StateTimeline, max_failed_frac: float) -> None:
    coverage = timeline.coverage
    if not coverage.done:
        return
    failed_frac = coverage.failed / coverage.done
    if failed_frac > max_failed_frac:
        raise TooManyFailedFramesError(
            f"{coverage.failed}/{coverage.done} frames failed schema validation "
            f"({failed_frac:.0%} > {max_failed_frac:.0%})"
        )


def _coverage_warnings(coverage: Coverage) -> list[str]:
    if coverage.mode == "partial":
        return [
            f"Deadline reached before the coarse sampling grid finished: only "
            f"{coverage.done}/{coverage.planned} frames were analysed."
        ]
    if coverage.mode == "coarse":
        return [
            f"Deadline reached during the fill pass: the coarse grid completed but only "
            f"{coverage.done}/{coverage.planned} frames were analysed overall."
        ]
    return []
