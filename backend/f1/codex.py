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


class Codex(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    source_workbook: str
    rules: list[Rule] = Field(min_length=1)


def load_codex(path: Path) -> Codex:
    with path.open(encoding="utf-8") as stream:
        codex = Codex.model_validate(yaml.safe_load(stream))
    ids = [rule.id for rule in codex.rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule IDs in codex")
    return codex
