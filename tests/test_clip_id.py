from __future__ import annotations

import pytest

from backend.clip_id import InvalidClipId, clip_number, parse_clip_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("X-1.mov", "X-1"),
        ("Х-10.mov", "X-10"),  # Cyrillic Х, as most organizer files are named
        ("х-10", "X-10"),  # Cyrillic lower case
        ("x 12.MOV", "X-12"),
        ("X–3", "X-3"),  # en dash
        ("X-003", "X-3"),
        (" X-48 ", "X-48"),
    ],
)
def test_parse_clip_id_accepts_organizer_spellings(text, expected):
    assert parse_clip_id(text) == expected


@pytest.mark.parametrize(
    "text",
    ["box12.mov", "X-12_done", "3f9a2c1e", "random.mov", "", "X-", "XX-1", "X-1.mp4", "Y-1"],
)
def test_parse_clip_id_rejects_anything_that_is_not_a_whole_clip_name(text):
    with pytest.raises(InvalidClipId):
        parse_clip_id(text)


def test_clip_number_orders_numerically():
    assert sorted(["X-10", "X-2", "X-1"], key=clip_number) == ["X-1", "X-2", "X-10"]
