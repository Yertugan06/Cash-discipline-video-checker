"""Serialize grounded findings into the jury's `DoneJob` contract.

Mapping (SHARED_BRIEF.md "WP1 serializer mapping"):
  Violation.type        = rule.title_ru
  description           = knowledge.describe(g)        (injected, see `Describe`)
  timecode_sec          = finding.t_anchor
  rule_id               = rule.rule_id
  source                = "<act>, <punkt>" of the primary norm (norm_ids[0])
  source_url            = primary norm's url
  source_quote          = primary norm's verbatim quote
  strength              = primary norm's strength
  citation_status       = g.citation_status
  verdict               = "violation" iff violations is non-empty
  coverage, warnings    copied from DetectionResult
"""

from __future__ import annotations

from collections.abc import Callable

from backend.contracts import DetectionResult, DoneJob, EvidenceFrame, GroundedFinding, Violation

Describe = Callable[[GroundedFinding], str]


class SerializeError(ValueError):
    """A grounded finding cannot be turned into a jury violation."""


def to_done_job(
    job_id: str,
    grounded: list[GroundedFinding],
    result: DetectionResult,
    evidence: list[list[EvidenceFrame]],
    describe: Describe,
) -> DoneJob:
    if len(evidence) != len(grounded):
        raise SerializeError("Evidence frames do not line up with grounded findings")
    violations = [
        _to_violation(g, frames, describe) for g, frames in zip(grounded, evidence, strict=True)
    ]
    return DoneJob(
        job_id=job_id,
        status="done",
        verdict="violation" if violations else "no_violation",
        violations=violations,
        warnings=list(result.warnings),
        coverage=result.coverage,
    )


def _to_violation(g: GroundedFinding, frames: list[EvidenceFrame], describe: Describe) -> Violation:
    if not g.rule.norm_ids or not g.norms:
        raise SerializeError(f"Rule {g.rule.rule_id} is enabled with no norms attached")
    primary_id = g.rule.norm_ids[0]
    primary = next((norm for norm in g.norms if norm.norm_id == primary_id), g.norms[0])
    return Violation(
        type=g.rule.title_ru,
        timecode_sec=g.finding.t_anchor,
        description=describe(g),
        evidence_frames=frames,
        rule_id=g.rule.rule_id,
        source=f"{primary.act}, {primary.punkt}",
        source_url=str(primary.url),
        source_quote=primary.quote,
        strength=g.rule.citation_strengths[primary_id],
        citation_status=g.citation_status,
        jurisdiction=primary.jurisdiction,
        document_title=primary.document_title,
        issuing_authority=primary.issuing_authority,
        act_number=primary.act_number,
        adopted_on=primary.adopted_on,
        detection_confidence=g.finding.detection_confidence,
        business_status=g.rule.business_status,
        implementation_status=g.rule.implementation_status,
    )
