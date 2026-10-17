import math
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Z]+-[A-Z-]+$")
    family: str
    requirement: str
    breach_condition: str
    signals: str
    min_duration_text: str
    min_duration_sec: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    timecode_anchor: str
    source: str = Field(min_length=1)
    source_url: str
    strength: str
    status: str
    title: str = ""
    description_template: str = ""
    title_en: str = ""
    description_template_en: str = ""

    @field_validator("source_url")
    @classmethod
    def http_source(cls, value: str) -> str:
        if not re.match(r"^https?://[^\s/]+", value):
            raise ValueError("source_url must be an HTTP(S) URL")
        return value


class ClipInfo(BaseModel):
    id: str
    camera_layout: str
    rule_ids: list[str]
    case_id: str | None
    duplicate_of: str | None


class Codex(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    source_workbook: str
    rules: list[Rule] = Field(min_length=1)
    clips: list[ClipInfo] = Field(default_factory=list)


def load_codex(path: Path) -> Codex:
    with path.open(encoding="utf-8") as stream:
        codex = Codex.model_validate(yaml.safe_load(stream))
    ids = [rule.id for rule in codex.rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule IDs in codex")
    clip_ids = [clip.id for clip in codex.clips]
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError("Duplicate clip IDs in codex")
    if any(rule_id not in ids for clip in codex.clips for rule_id in clip.rule_ids):
        raise ValueError("Clip refers to an unknown rule ID")
    return codex


def duration_seconds(value: str) -> float | None:
    # Ambiguous proposals remain text; an engine must not invent a threshold.
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*s\s*", value)
    if not match:
        return None
    result = float(match[1])
    return result if math.isfinite(result) else None


def rules_markdown(codex: Codex) -> str:
    parts = [
        "# Rules\n",
        "Generated from codex.yaml. Source citations are workbook data, not a legal review.\n",
        f"Implemented in v1: {sum(bool(r.description_template) for r in codex.rules)} detectors. "
        "Other entries remain in evaluation as known misses.\n",
    ]
    for rule in codex.rules:
        parts.append(
            f"## {rule.id}\n\n{rule.breach_condition}\n\n"
            f"Duration proposal: {rule.min_duration_text}. Anchor: {rule.timecode_anchor}.\n\n"
            f"Source: [{rule.source}]({rule.source_url}). "
            f"Strength: {rule.strength}. Status: {rule.status}.\n"
        )
    return "\n".join(parts)
