"""Integration tests for `backend.pipeline.Pipeline`: probe -> plan -> detect ->
rank -> ground -> evidence -> serialize, with a fake detector/knowledge but
real `backend.media` (so these need real ffmpeg/ffprobe; see conftest)."""

from __future__ import annotations

import time

import pytest

from backend.config import ROOT
from backend.contracts import Coverage
from backend.pipeline import IncompleteAnalysisError, Pipeline
from tests.conftest import (
    FakeDetector,
    FakeKnowledge,
    identity_rank,
    make_finding,
    requires_ffmpeg,
)


@requires_ffmpeg
def test_run_produces_a_done_job_with_evidence_from_the_source_video(video):
    detector = FakeDetector(findings=[make_finding("T-RULE", t_anchor=0.4)])
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    job = pipeline.run("job-x", video, deadline_monotonic=time.monotonic() + 60)
    assert job.job_id == "job-x" and job.status == "done"
    assert job.verdict == "violation"
    assert len(job.violations) == 1
    violation = job.violations[0]
    assert violation.rule_id == "T-RULE"
    assert 1 <= len(violation.evidence_frames) <= 3
    for evidence_frame in violation.evidence_frames:
        assert evidence_frame.image_base64


@requires_ffmpeg
def test_run_with_no_findings_is_no_violation(video):
    detector = FakeDetector(findings=[])
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    job = pipeline.run("job-y", video, deadline_monotonic=time.monotonic() + 60)
    assert job.verdict == "no_violation"
    assert job.violations == []


@requires_ffmpeg
def test_detector_passes_through_the_video_info_and_the_deadline(video):
    detector = FakeDetector(findings=[])
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    deadline = time.monotonic() + 123.0
    pipeline.run("job-z", video, deadline_monotonic=deadline)
    assert len(detector.calls) == 1
    called_video, info, plan = detector.calls[0]
    assert called_video == video
    # The finalize reserve keeps ranking, evidence and serialization inside the job deadline.
    assert plan.deadline_monotonic == deadline - pipeline.finalize_reserve_s
    assert info.duration_sec > 0


def _partial_coverage() -> Coverage:
    return Coverage(step_s=0.5, planned=20, done=8, failed=0, deadline_hit=True, mode="partial")


@requires_ffmpeg
def test_partial_coverage_without_findings_is_not_reported_as_no_violation(video):
    detector = FakeDetector(findings=[], coverage=_partial_coverage())
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    with pytest.raises(IncompleteAnalysisError, match="8 of 20"):
        pipeline.run("job-partial", video, deadline_monotonic=time.monotonic() + 60)


@requires_ffmpeg
def test_partial_coverage_keeps_the_findings_it_has(video):
    detector = FakeDetector(
        findings=[make_finding("T-RULE", t_anchor=0.4)], coverage=_partial_coverage()
    )
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    job = pipeline.run("job-partial-found", video, deadline_monotonic=time.monotonic() + 60)
    assert job.verdict == "violation"
    assert job.coverage.deadline_hit and job.coverage.mode == "partial"


@requires_ffmpeg
def test_detector_errors_propagate_unchanged(video):
    detector = FakeDetector(error=RuntimeError("boom"))
    pipeline = Pipeline(detector=detector, rank=identity_rank, knowledge=FakeKnowledge())
    with pytest.raises(RuntimeError, match="boom"):
        pipeline.run("job-e", video, deadline_monotonic=time.monotonic() + 60)


@requires_ffmpeg
def test_ranking_caps_the_findings_before_grounding(video):
    findings = [make_finding("T-RULE", t_anchor=t) for t in (0.1, 0.2, 0.3, 0.4)]
    detector = FakeDetector(findings=findings)
    pipeline = Pipeline(
        detector=detector, rank=identity_rank, knowledge=FakeKnowledge(), rank_cap=2
    )
    job = pipeline.run("job-cap", video, deadline_monotonic=time.monotonic() + 60)
    assert len(job.violations) == 2


@requires_ffmpeg
def test_unknown_rule_id_from_the_detector_fails_loudly(video):
    detector = FakeDetector(findings=[make_finding("NO-SUCH-RULE")])
    pipeline = Pipeline(detector=detector, rank=lambda f, r, c: f, knowledge=FakeKnowledge())
    with pytest.raises(StopIteration):
        pipeline.run("job-u", video, deadline_monotonic=time.monotonic() + 60)


@requires_ffmpeg
def test_pipeline_runs_against_wp3s_real_knowledge_and_rank(video):
    """SHARED_BRIEF.md: once WP3's real modules exist, run the pipeline
    against them too, not just the fakes above."""
    from backend.knowledge import Knowledge
    from backend.rules import rank as real_rank

    knowledge = Knowledge.load(ROOT / "knowledge")
    finding = make_finding("W-NO-FOOD", t_anchor=1.0)
    detector = FakeDetector(findings=[finding])
    pipeline = Pipeline(detector=detector, rank=real_rank, knowledge=knowledge)
    job = pipeline.run("job-real-knowledge", video, deadline_monotonic=time.monotonic() + 60)
    assert job.verdict == "violation"
    violation = job.violations[0]
    assert violation.rule_id == "W-NO-FOOD"
    assert violation.type == knowledge.rule("W-NO-FOOD").title_ru
    assert violation.description  # knowledge.describe() filled the real template
    assert violation.source and violation.source_url and violation.citation_status
