"""Shared test doubles and fixtures for WP1's test suite.

Most API/worker/store tests inject a fully fake `Pipeline` (see `FakePipeline`)
so they never need ffmpeg. `test_pipeline.py` exercises the real
`backend.pipeline.Pipeline` with a fake detector/knowledge but real
`backend.media`, gated by `shutil.which("ffmpeg")` per SHARED_BRIEF.md.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from backend.contracts import (
    Coverage,
    DetectionResult,
    Finding,
    GroundedFinding,
    NormRef,
    RuleEntry,
    SamplingPlan,
    VideoInfo,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(
    not (HAS_FFMPEG and HAS_FFPROBE), reason="ffmpeg/ffprobe not installed on this machine"
)


def make_video(path: Path, *, duration: float = 1.0, width: int = 64, height: int = 96) -> Path:
    """Render a tiny, real .mov with ffmpeg. Caller must guard with `requires_ffmpeg`."""
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:s={width}x{height}:r=10:d={duration}",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def video(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    duration = getattr(request, "param", 1.0)
    return make_video(tmp_path / "clip.mov", duration=duration)


def make_norm(norm_id: str = "N-1", *, human_verified: bool = True) -> NormRef:
    return NormRef(
        norm_id=norm_id,
        act="Test act",
        punkt="п. 1",
        quote="Verbatim quote.",
        url="https://adilet.zan.kz/rus/docs/TEST",
        strength="direct",
        human_verified=human_verified,
        verified_by="tester" if human_verified else None,
        verified_at=date(2026, 1, 1) if human_verified else None,
    )


def make_rule(rule_id: str = "T-RULE", *, norm_ids: list[str] | None = None) -> RuleEntry:
    return RuleEntry(
        rule_id=rule_id,
        title_ru="Тестовое правило",
        title_en="Test rule",
        mechanism="test",
        states_used=[],
        params={},
        description_template="С {t_start} по {t_end} с: тест.",
        visibility_caveat="",
        norm_ids=norm_ids if norm_ids is not None else ["N-1"],
        enabled=True,
    )


def make_finding(rule_id: str = "T-RULE", t_anchor: float = 1.0) -> Finding:
    return Finding(
        rule_id=rule_id,
        t_anchor=t_anchor,
        t_start=t_anchor,
        t_end=t_anchor,
        support_t=[t_anchor],
        facts={"t_start": t_anchor, "t_end": t_anchor},
        rank_score=1.0,
    )


@dataclass
class FakeDetector:
    """A `Detector` test double: returns a canned result, or raises `error`."""

    findings: list[Finding] = field(default_factory=list)
    coverage: Coverage = field(
        default_factory=lambda: Coverage(
            step_s=0.5, planned=1, done=1, failed=0, deadline_hit=False, mode="full"
        )
    )
    warnings: list[str] = field(default_factory=list)
    error: Exception | None = None
    calls: list[tuple[Path, VideoInfo, SamplingPlan]] = field(default_factory=list)

    def detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult:
        self.calls.append((video, info, plan))
        if self.error is not None:
            raise self.error
        return DetectionResult(
            findings=self.findings, coverage=self.coverage, warnings=self.warnings
        )


@dataclass
class FakeKnowledge:
    """A `KnowledgeLike` test double (SHARED_BRIEF.md: use a fake until WP3's
    module exists -- also handy now to isolate pipeline tests from the real
    Knowledge Pack's content)."""

    rules: list[RuleEntry] = field(default_factory=lambda: [make_rule()])
    norms: dict[str, NormRef] = field(default_factory=lambda: {"N-1": make_norm()})

    def enabled_rules(self) -> list[RuleEntry]:
        return [r for r in self.rules if r.enabled]

    def rule(self, rule_id: str) -> RuleEntry:
        return next(r for r in self.rules if r.rule_id == rule_id)

    def ground(self, findings: list[Finding]) -> list[GroundedFinding]:
        grounded = []
        for finding in findings:
            rule = self.rule(finding.rule_id)
            norms = [self.norms[nid] for nid in rule.norm_ids]
            status = "verified" if all(n.human_verified for n in norms) else "needs_review"
            grounded.append(
                GroundedFinding(finding=finding, rule=rule, norms=norms, citation_status=status)
            )
        return grounded

    def describe(self, g: GroundedFinding) -> str:
        facts = dict(g.finding.facts)
        facts.setdefault("t", round(g.finding.t_anchor, 1))
        return g.rule.description_template.format(**facts) + f" {g.rule.title_ru}."


def identity_rank(findings: list[Finding], rules: list[RuleEntry], cap: int = 3) -> list[Finding]:
    known = {r.rule_id for r in rules}
    return [f for f in findings if f.rule_id in known][:cap]


@dataclass
class FakePipeline:
    """A fully fake `Pipeline`-shaped object for API/worker/store tests that
    must not depend on ffmpeg at all."""

    result: object = None
    error: Exception | None = None
    calls: list[tuple[str, Path, float]] = field(default_factory=list)

    def run(self, job_id: str, video: Path, deadline_monotonic: float):
        self.calls.append((job_id, video, deadline_monotonic))
        if self.error is not None:
            raise self.error
        assert self.result is not None, "FakePipeline needs a canned `result` or an `error`"
        return self.result
