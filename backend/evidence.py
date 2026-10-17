"""Evidence frames: 1-3 JPEGs cut directly from the source video.

Frames are always re-extracted from the original upload at `t_anchor` and
the nearest `support_t` via `backend.media.extract_jpeg` -- never from the
detector's own (possibly downscaled) sampling frames. When the detector
reports `Finding.boxes`, they are drawn on the anchor frame only: the boxes
describe the scene at `t_anchor`, and the object may have moved by the
support frame.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.contracts import EvidenceBox, EvidenceFrame, GroundedFinding
from backend.media import MediaError, extract_jpeg

MAX_FRAMES = 3
BOX_COLOR = (255, 32, 32)


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
        if t == anchor and finding.boxes:
            jpeg = draw_boxes(jpeg, finding.boxes)
        frames.append(
            EvidenceFrame(timestamp_sec=t, image_base64=base64.b64encode(jpeg).decode("ascii"))
        )
    if not frames:
        raise MediaError(f"Could not extract an evidence frame for rule {finding.rule_id}")
    return frames


def draw_boxes(jpeg: bytes, boxes: list[EvidenceBox]) -> bytes:
    """Outline each normalized box on the frame, with its label above it."""
    with Image.open(io.BytesIO(jpeg)) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    line = max(2, round(min(width, height) / 200))
    font = ImageFont.load_default(size=max(12, round(min(width, height) / 30)))
    for item in boxes:
        x1, y1, x2, y2 = item.box
        rect = (x1 * width, y1 * height, x2 * width, y2 * height)
        draw.rectangle(rect, outline=BOX_COLOR, width=line)
        left, top, right, bottom = draw.textbbox((0, 0), item.label, font=font)
        label_w, label_h = right - left + 2 * line, bottom - top + 2 * line
        label_y = rect[1] - label_h if rect[1] >= label_h else rect[1]
        draw.rectangle((rect[0], label_y, rect[0] + label_w, label_y + label_h), fill=BOX_COLOR)
        draw.text(
            (rect[0] + line - left, label_y + line - top), item.label, fill="white", font=font
        )
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def _nearest_support(support_t: list[float], anchor: float) -> float | None:
    if not support_t:
        return None
    return min(support_t, key=lambda t: abs(t - anchor))
