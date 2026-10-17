"""Pure tests for `backend.serialize.to_done_job` (no ffmpeg, no real Knowledge Pack)."""

from __future__ import annotations

import pytest

from backend.contracts import Coverage, DetectionResult, EvidenceFrame, GroundedFinding
from backend.serialize import SerializeError, to_done_job
from tests.conftest import make_finding, make_norm, make_rule

TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def frame(t: float = 1.0) -> EvidenceFrame:
    import base64

    return EvidenceFrame(timestamp_sec=t, image_base64=base64.b64encode(TINY_JPEG).decode())


def coverage(mode: str = "full") -> Coverage:
    return Coverage(step_s=0.5, planned=10, done=10, failed=0, deadline_hit=False, mode=mode)


def describe(g: GroundedFinding) -> str:
    return f"description for {g.rule.rule_id}"


def test_no_violations_means_no_violation_verdict():
    result = DetectionResult(findings=[], coverage=coverage(), warnings=[])
    job = to_done_job("job-1", [], result, [], describe)
    assert job.verdict == "no_violation"
    assert job.violations == []
    assert job.job_id == "job-1" and job.status == "done"


def test_one_grounded_finding_maps_to_a_violation_with_the_primary_norm():
    rule = make_rule("T-RULE", norm_ids=["N-primary", "N-secondary"])
    primary = make_norm("N-primary")
    secondary = make_norm("N-secondary")
    finding = make_finding("T-RULE", t_anchor=12.5)
    grounded = GroundedFinding(
        finding=finding, rule=rule, norms=[primary, secondary], citation_status="verified"
    )
    result = DetectionResult(findings=[finding], coverage=coverage(), warnings=["partial"])
    job = to_done_job("job-2", [grounded], result, [[frame(12.5)]], describe)
    assert job.verdict == "violation"
    assert job.warnings == ["partial"]
    assert job.coverage == result.coverage
    violation = job.violations[0]
    assert violation.type == rule.title_ru
    assert violation.timecode_sec == 12.5
    assert violation.description == "description for T-RULE"
    assert violation.rule_id == "T-RULE"
    assert violation.source == f"{primary.act}, {primary.punkt}"
    assert violation.source_url == str(primary.url)
    assert violation.source_quote == primary.quote
    assert violation.strength == primary.strength
    assert violation.citation_status == "verified"
    assert len(violation.evidence_frames) == 1


def test_rule_without_norms_is_rejected_rather_than_silently_dropped():
    rule = make_rule("T-RULE", norm_ids=[])
    finding = make_finding("T-RULE")
    grounded = GroundedFinding(finding=finding, rule=rule, norms=[], citation_status="needs_review")
    result = DetectionResult(findings=[finding], coverage=coverage(), warnings=[])
    with pytest.raises(SerializeError):
        to_done_job("job-3", [grounded], result, [[frame()]], describe)


def test_evidence_list_must_line_up_with_grounded_findings():
    rule = make_rule()
    finding = make_finding()
    grounded = GroundedFinding(
        finding=finding, rule=rule, norms=[make_norm()], citation_status="verified"
    )
    result = DetectionResult(findings=[finding], coverage=coverage(), warnings=[])
    with pytest.raises(SerializeError):
        to_done_job("job-4", [grounded], result, [], describe)
