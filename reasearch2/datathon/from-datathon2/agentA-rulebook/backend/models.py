import base64
import binascii
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class EvidenceFrame(ContractModel):
    timestamp_sec: float = Field(ge=0)
    image_base64: str

    @field_validator("image_base64")
    @classmethod
    def jpeg_only(cls, value: str) -> str:
        try:
            content = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Evidence must be base64 JPEG") from exc
        if not content.startswith(b"\xff\xd8\xff") or not content.endswith(b"\xff\xd9"):
            raise ValueError("Evidence must be base64 JPEG")
        return value


class Violation(ContractModel):
    type: str = Field(min_length=1)
    timecode_sec: float = Field(ge=0)
    description: str = Field(min_length=1)
    evidence_frames: list[EvidenceFrame] = Field(min_length=1, max_length=3)
    rule_id: str
    source: str
    source_url: str
    strength: str
    confidence: float = Field(ge=0, le=1)
    type_en: str = ""
    description_en: str = ""


class Event(ContractModel):
    timestamp_sec: float = Field(ge=0)
    type: str
    facts: dict[str, str | int | float | bool | list[float] | list[str]] = Field(
        default_factory=dict
    )


class VideoMetadata(ContractModel):
    duration_sec: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sample_fps: float = Field(gt=0)
    sampled_frames: int = Field(gt=0)


class AnalysisResult(ContractModel):
    verdict: Literal["violation", "no_violation"]
    violations: list[Violation]
    analysis_stage: Literal["complete"] = "complete"
    warnings: list[str]
    runtime_sec: float = Field(ge=0)
    video: VideoMetadata
    events: list[Event]
    debug_available: bool = False
    coverage: dict[str, bool] = Field(default_factory=dict)
    perception_cached: bool = False

    @model_validator(mode="after")
    def consistent_verdict(self) -> Self:
        expected = "violation" if self.violations else "no_violation"
        if self.verdict != expected:
            raise ValueError("verdict must agree with violations")
        times = [v.timecode_sec for v in self.violations]
        if times != sorted(times):
            raise ValueError("violations must be sorted by timecode_sec")
        if any(t > self.video.duration_sec for t in times):
            raise ValueError("violation timecode exceeds video duration")
        return self


class AcceptedJob(BaseModel):
    job_id: str


class ProcessingJob(AcceptedJob):
    status: Literal["processing"] = "processing"


class FailedJob(AcceptedJob):
    status: Literal["failed"] = "failed"
    error: str


class DoneJob(AnalysisResult):
    job_id: str
    status: Literal["done"] = "done"
