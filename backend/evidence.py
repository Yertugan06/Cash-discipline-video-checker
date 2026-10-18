"""Evidence frames: 1-3 JPEGs cut directly from the source video.

Each finding gets a before / moment / after triple: `t_anchor - CONTEXT_S`,
`t_anchor` and `t_anchor + CONTEXT_S`, clamped to the video, so a reviewer
sees what led up to the moment and what followed it. Times that clamp onto
the same frame (a finding near the start or end) are shown once.

Frames are always re-extracted from the original upload via
`backend.media.extract_jpeg` -- never from the detector's own (possibly
downscaled) sampling frames. When the detector reports `Finding.boxes`, they
are drawn on the anchor frame only: the boxes describe the scene at
`t_anchor`, and the object may have moved by the context frames.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.contracts import EvidenceBox, EvidenceFrame, GroundedFinding
from backend.media import MediaError, extract_jpeg

MAX_FRAMES = 3
CONTEXT_S = 2.0  # offset of the before / after frames from t_anchor
BOX_COLOR = (255, 32, 32)


def collect(
    video: Path, grounded: list[GroundedFinding], last_frame_sec: float
) -> list[list[EvidenceFrame]]:
    """Return one evidence-frame list per grounded finding, same order as `grounded`.

    `last_frame_sec` is the time of the video's last decodable frame (duration - 1/fps): findings
    may be anchored up to the very end, where there is no frame, so later times show that frame
    and say so in `timestamp_sec`.
    """
    return [_frames_for(video, g, last_frame_sec) for g in grounded]


def _frames_for(video: Path, g: GroundedFinding, last_frame_sec: float) -> list[EvidenceFrame]:
    finding = g.finding
    anchor = finding.t_anchor
    times = [anchor - CONTEXT_S, anchor, anchor + CONTEXT_S]
    frames: list[EvidenceFrame] = []
    for t in times[:MAX_FRAMES]:
        shown = min(max(t, 0.0), last_frame_sec)
        if any(abs(f.timestamp_sec - shown) < 1e-6 for f in frames):
            continue
        try:
            jpeg = extract_jpeg(video, shown)
        except MediaError:
            continue
        if t == anchor and finding.boxes:
            jpeg = draw_boxes(jpeg, finding.boxes)
        frames.append(
            EvidenceFrame(timestamp_sec=shown, image_base64=base64.b64encode(jpeg).decode("ascii"))
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
