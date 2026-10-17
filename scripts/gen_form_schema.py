"""Generates `backend/vlm/form_schema.json` from `backend.contracts.FrameState`.

`backend/vlm/form_schema.json` must never be hand-edited (AGENTS.md "one
authoritative implementation"; it is the vLLM structured-output schema sent
with every request in `backend.vlm.client`). This script is that one
authoritative source. `tests/test_vlm_schema.py` asserts the committed file
still matches `build_schema()`'s current output.

Usage:
    .venv/bin/python scripts/gen_form_schema.py
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.contracts import FrameState

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "backend" / "vlm" / "form_schema.json"


def build_schema() -> dict:
    """The vLLM structured-output JSON schema for one frame's questionnaire answer.

    Derived from `FrameState.model_json_schema()`:
      - per-field `title`s are dropped (pydantic adds them; vLLM/the model
        does not need them);
      - the model-level `description` (a docstring about this port, not about
        the schema) is dropped;
      - `additionalProperties: false` is added so the model cannot emit the
        kit's free-text `other` field (architecture.md §3: "The questionnaire's
        free-text `other` field is dropped") or anything else; `FrameState`
        itself already has no `other` field, so there is nothing else to
        remove here.
    """
    schema = FrameState.model_json_schema()
    schema.pop("description", None)
    schema["title"] = "cash_desk_frame_state_v1"
    schema["additionalProperties"] = False
    for prop in schema["properties"].values():
        prop.pop("title", None)
    return schema


def main() -> None:
    SCHEMA_PATH.write_text(
        json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
