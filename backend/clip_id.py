"""Clip ID: the canonical name of one organizer file, `X-<n>` with a Latin X (GLOSSARY.md).

The only parser for clip IDs. Organizer files mix Latin `X-1.mov` with Cyrillic `Х-10.mov`, so
both letters are accepted; anything that is not a whole clip name is rejected rather than guessed.
User uploads and job IDs are not clip IDs and must not be passed through this.
"""

from __future__ import annotations

import re

_CLIP_ID = re.compile(r"[XxХх]\s*[-–]?\s*(\d+)")


class InvalidClipId(ValueError):
    pass


def parse_clip_id(text: str) -> str:
    """'Х-10.mov' / 'x 12' / 'X–003' -> 'X-10' / 'X-12' / 'X-3'; raises InvalidClipId otherwise."""
    stem = text.strip()
    if stem.lower().endswith(".mov"):
        stem = stem[:-4].rstrip()
    match = _CLIP_ID.fullmatch(stem)
    if not match:
        raise InvalidClipId(f"not a clip ID: {text!r}")
    return f"X-{int(match[1])}"


def clip_number(clip_id: str) -> int:
    """'X-12' -> 12, for ordering clip IDs numerically."""
    return int(parse_clip_id(clip_id)[2:])
