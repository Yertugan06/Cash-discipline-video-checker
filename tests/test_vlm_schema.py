"""form_schema.json must stay generated from contracts.FrameState (WP2 "Done when")."""

import json
from pathlib import Path

from scripts.gen_form_schema import SCHEMA_PATH, build_schema


def test_form_schema_matches_frame_state() -> None:
    on_disk = json.loads(Path(SCHEMA_PATH).read_text(encoding="utf-8"))
    assert on_disk == build_schema(), (
        "backend/vlm/form_schema.json is out of sync with contracts.FrameState; "
        "regenerate it with `.venv/bin/python scripts/gen_form_schema.py`"
    )


def test_form_schema_drops_other_field() -> None:
    schema = build_schema()
    assert "other" not in schema["properties"]
    assert "other" not in schema["required"]
    assert schema["additionalProperties"] is False
