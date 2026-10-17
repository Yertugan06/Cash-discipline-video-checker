"""Evidence frames: 1-3 JPEGs cut directly from the source video.

Frames are always re-extracted from the original upload at `t_anchor` and
the nearest `support_t` via `backend.media.extract_jpeg` -- never from the
detector's own (possibly downscaled) sampling frames.
"""

from __future__ import annotations

import base64
from pathlib import Path

from backend.contracts import EvidenceFrame, GroundedFinding
from backend.media import MediaError, extract_jpeg

MAX_FRAMES = 3


def collect(video: Path, grounded: list[GroundedFinding]) -> list[list[EvidenceFrame]]:
    """Return one evidence-frame list per grounded finding, same order as `grounded`."""
    return [_frames_for(video, g) for g in grounded]


def _frames_for(video: Path, g: GroundedFinding) -> list[EvidenceFrame]:
    finding = g.finding
    anchor = finding.t_anchor
    times = [anchor]
    nearest = _nearest_support(finding.support_t, anchor)
    if nearest is not None and abs(nearest - anchor) > 1e-6:
        times.append(nearest)
    frames: list[EvidenceFrame] = []
    for t in times[:MAX_FRAMES]:
        try:
            jpeg = extract_jpeg(video, t)
        except MediaError:
            continue
        frames.append(
            EvidenceFrame(timestamp_sec=t, image_base64=base64.b64encode(jpeg).decode("ascii"))
        )
    if not frames:
        raise MediaError(f"Could not extract an evidence frame for rule {finding.rule_id}")
    return frames


def _nearest_support(support_t: list[float], anchor: float) -> float | None:
    if not support_t:
        return None
    return min(support_t, key=lambda t: abs(t - anchor))
