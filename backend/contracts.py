"""Frozen component contracts (ADR-002 / architecture.md §2).

Every module boundary in the pipeline is typed here. This is the single
authoritative source for shapes crossing those boundaries; nothing else
in backend/ should redefine them. Changing a type here requires notifying
every work-package owner (AGENTS.md "Multi-Agent Collaboration").
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, HttpUrl

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


class VideoInfo(BaseModel):
    sha256: str
    duration_sec: float = Field(gt=0, le=180)
    width: int
    height: int
    fps: float


class SamplingPlan(BaseModel):
    coarse_t: list[float]  # 4 s grid over [0, duration], always includes the last second
    fill_t: list[float]  # 2 s midpoints, processed only while budget remains
    deadline_monotonic: float  # absolute; derived from upload time + 270 s


# ---------------------------------------------------------------------------
# Perception (VLM questionnaire)
# ---------------------------------------------------------------------------

SafeDoor = Literal["open", "closed", "not_visible"]
Screen = Literal["unlocked", "lock_screen", "off_or_closed", "not_visible"]
KeyInLock = Literal["yes", "no", "not_visible"]
CashIn = Literal["nobody", "cashier", "client", "collector", "several"]
CashierAction = Literal[
    "not_present",
    "seated_idle",
    "working_on_laptop",
    "counting_by_hand",
    "using_counting_machine",
    "using_detector",
    "receiving_cash",
    "handing_cash_to_client",
    "checking_id_document",
    "at_safe",
    "packing_or_opening_bag",
    "walking_in",
    "walking_out",
    "eating_drinking",
    "using_phone",
    "other",
]


class FrameState(BaseModel):
    """= FEATURES.md v1/v2. The schema's free-text `other` field is dropped
    here: it is never used for routing or display (architecture.md §3)."""

    cashier_at_desk: bool
    cashier_in_room: bool
    people_cashier_side: int = Field(ge=0, le=5)
    clients_at_desk: int = Field(ge=0, le=5)
    person_at_door: bool
    collector_present: bool
    desk_cash: bool
    desk_bag: bool
    desk_documents: bool
    desk_personal_items: bool
    desk_food_drink: bool
    phone_in_cashier_hand: bool
    id_document_visible: bool
    counting_machine_in_use: bool
    detector_in_use: bool
    safe_door: SafeDoor
    key_in_safe_lock: KeyInLock
    laptop_screen: Screen
    room_door: SafeDoor
    cash_in_hands_of: CashIn
    cashier_action: CashierAction


class FrameObservation(BaseModel):
    t: float
    ok: bool
    state: FrameState | None = None
    error: str | None = None
    latency_s: float


class Coverage(BaseModel):
    step_s: float
    planned: int
    done: int
    failed: int
    deadline_hit: bool
    mode: Literal["full", "coarse", "partial"]


class StateTimeline(BaseModel):
    video: VideoInfo
    frames: list[FrameObservation]
    coverage: Coverage


# ---------------------------------------------------------------------------
# Detection seam (both detectors implement this)
# ---------------------------------------------------------------------------


class EvidenceBox(BaseModel):
    label: str  # what the detector saw, e.g. "handbag"
    box: tuple[float, float, float, float]  # x1, y1, x2, y2, normalized to [0, 1]


class Finding(BaseModel):
    rule_id: str  # canonical id from knowledge/rules.yaml
    t_anchor: float  # reported timecode
    t_start: float
    t_end: float  # supporting interval
    support_t: list[float]  # sampled times that satisfied the condition
    facts: dict[str, str | int | float | bool]  # template slots, e.g. away_s, object
    rank_score: float  # persistence-based; ranking frozen on dev
    detection_confidence: float | None = Field(default=None, ge=0, le=1)
    # Objects behind the finding at t_anchor, drawn on the anchor evidence frame.
    # Optional: the VLM detector reports no geometry.
    boxes: list[EvidenceBox] = Field(default_factory=list)


class DetectionResult(BaseModel):
    findings: list[Finding]
    coverage: Coverage
    warnings: list[str] = Field(default_factory=list)


class Detector(Protocol):
    def detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult: ...


# ---------------------------------------------------------------------------
# Knowledge pack
# ---------------------------------------------------------------------------


class NormRef(BaseModel):
    norm_id: str
    jurisdiction: Literal["KZ"]
    document_title: str
    act_short_title: str  # nominative name for citations, e.g. "Правила ..."
    issuing_authority: str
    act: str
    act_number: str
    adopted_on: date
    punkt: str
    quote: str
    url: HttpUrl
    citation_status: Literal["verified", "pending", "invalid"]
    verified_by: str | None = None
    verified_at: date | None = None


RuleScope = Literal["detector", "jury"]


class RuleEntry(BaseModel):
    rule_id: str
    business_status: Literal["confirmed", "candidate"]
    implementation_status: Literal["implemented", "unimplemented"]
    title_ru: str
    title_en: str
    mechanism: str
    states_used: list[str]
    params: dict[str, float]
    description_template: str  # slots from Finding.facts plus {t}
    visibility_caveat: str  # what the video cannot establish
    norm_ids: list[str]  # first = primary citation
    citation_strengths: dict[str, Literal["direct", "indirect", "weak"]]
    enabled: bool  # the detector runs it
    disabled_reason: str | None = None
    # Enabled, and every cited norm and its act are human-verified (knowledge/rulebook.yaml).
    # Only these are reported under RULE_SCOPE=jury.
    jury_eligible: bool = False


class GroundedFinding(BaseModel):
    finding: Finding
    rule: RuleEntry
    norms: list[NormRef]
    citation_status: Literal["verified", "pending", "invalid"]
    observation: str  # rule.description_template filled with the finding's facts


# ---------------------------------------------------------------------------
# API (jury contract unchanged; extras optional)
# ---------------------------------------------------------------------------


class EvidenceFrame(BaseModel):
    timestamp_sec: float
    image_base64: str  # JPEG only


class LegalBasis(BaseModel):
    """One norm a violation cites, ready for display; the first in `Violation.legal_basis` is the
    primary citation."""

    norm_id: str
    citation: str  # human-readable reference: act short title, punkt, authority, number, date
    act_short_title: str
    punkt: str
    quote: str
    url: str
    strength: Literal["direct", "indirect", "weak"]
    citation_status: Literal["verified", "pending", "invalid"]
    document_title: str
    issuing_authority: str
    act_number: str
    adopted_on: date


class Violation(BaseModel):
    # jury-required fields (task.md §10) -- never rename, never add a required one
    type: str
    timecode_sec: float
    description: str
    evidence_frames: list[EvidenceFrame] = Field(min_length=1, max_length=3)
    # optional extras, used by the UI only
    rule_id: str | None = None
    source: str | None = None
    source_url: str | None = None
    source_quote: str | None = None  # verbatim norm text for the UI norm block
    strength: str | None = None
    citation_status: Literal["verified", "pending", "invalid"] | None = None
    jurisdiction: str | None = None
    document_title: str | None = None
    issuing_authority: str | None = None
    act_number: str | None = None
    adopted_on: date | None = None
    detection_confidence: float | None = Field(default=None, ge=0, le=1)
    business_status: Literal["confirmed", "candidate"] | None = None
    implementation_status: Literal["implemented", "unimplemented"] | None = None
    # structured explanation, so the UI need not parse `description`
    observation: str | None = None  # what the video shows
    t_start_sec: float | None = None  # supporting interval
    t_end_sec: float | None = None
    visibility_caveat: str | None = None  # what the video cannot establish
    legal_basis: list[LegalBasis] | None = None  # every cited norm, primary first


class DoneJob(BaseModel):
    job_id: str
    status: Literal["done"]
    verdict: Literal["violation", "no_violation"]
    violations: list[Violation]
    warnings: list[str] = Field(default_factory=list)
    coverage: Coverage | None = None


class ProcessingJob(BaseModel):
    job_id: str
    status: Literal["processing"]


class FailedJob(BaseModel):
    job_id: str
    status: Literal["failed"]
    error: str


class AcceptedJob(BaseModel):
    job_id: str


JobResult = DoneJob | ProcessingJob | FailedJob
