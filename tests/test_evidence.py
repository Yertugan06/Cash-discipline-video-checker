"""Tests for `backend.evidence`: before / moment / after frames and box overlays."""

from __future__ import annotations

import base64
import io

from PIL import Image

from backend.contracts import EvidenceBox, GroundedFinding
from backend.evidence import BOX_COLOR, CONTEXT_S, collect, draw_boxes
from tests.conftest import make_finding, make_norm, make_rule, make_video, requires_ffmpeg


def _jpeg(width: int = 1200, height: int = 800) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), (0, 128, 0)).save(output, format="JPEG")
    return output.getvalue()


def _is_box_color(pixel: tuple[int, int, int]) -> bool:
    return all(abs(a - b) < 60 for a, b in zip(pixel, BOX_COLOR, strict=True))


def test_draw_boxes_outlines_the_normalized_box_and_keeps_the_frame_size():
    out = draw_boxes(_jpeg(), [EvidenceBox(label="handbag", box=(0.25, 0.5, 0.75, 0.9))])
    with Image.open(io.BytesIO(out)) as image:
        assert image.size == (1200, 800)
        rgb = image.convert("RGB")
        # line width is 4 px at this size; sample the middle of each stroke
        assert _is_box_color(rgb.getpixel((600, 718)))  # bottom edge (y2 = 720)
        assert _is_box_color(rgb.getpixel((302, 600)))  # left edge (x1 = 300)
        assert not _is_box_color(rgb.getpixel((600, 600)))  # interior untouched
        assert not _is_box_color(rgb.getpixel((1150, 50)))  # outside untouched


def _grounded(finding):
    return GroundedFinding(
        finding=finding,
        rule=make_rule(),
        norms=[make_norm()],
        citation_status="verified",
        observation="observation",
    )


def test_collect_shows_before_moment_and_after_the_anchor(tmp_path, monkeypatch):
    cut: list[float] = []
    monkeypatch.setattr(
        "backend.evidence.extract_jpeg", lambda video, t: cut.append(t) or _jpeg(64, 96)
    )
    frames = collect(tmp_path / "clip.mov", [_grounded(make_finding(t_anchor=30.0))], 59.9)[0]
    expected = [30.0 - CONTEXT_S, 30.0, 30.0 + CONTEXT_S]
    assert [f.timestamp_sec for f in frames] == expected
    assert cut == expected


@requires_ffmpeg
def test_collect_draws_boxes_on_the_anchor_frame_only(tmp_path):
    video = make_video(tmp_path / "big.mov", width=1200, height=800)
    box = EvidenceBox(label="bag", box=(0.25, 0.25, 0.75, 0.75))
    finding = make_finding(t_anchor=0.2).model_copy(update={"boxes": [box]})
    frames = collect(video, [_grounded(finding)], last_frame_sec=0.9)[0]
    # before / after clamp to the first and last frame of the 1 s clip
    assert [f.timestamp_sec for f in frames] == [0.0, 0.2, 0.9]
    bottom_edges = []
    for frame in frames:
        with Image.open(io.BytesIO(base64.b64decode(frame.image_base64))) as image:
            bottom_edges.append(image.convert("RGB").getpixel((600, 598)))  # y2 = 600
    assert [_is_box_color(pixel) for pixel in bottom_edges] == [False, True, False]


@requires_ffmpeg
def test_a_finding_at_the_very_end_still_gets_the_last_frame(tmp_path):
    # F1 accepts findings up to t == duration; ffmpeg has no frame there. The job must not fail.
    video = make_video(tmp_path / "end.mov", duration=1.0)
    finding = make_finding(t_anchor=1.0)
    frames = collect(video, [_grounded(finding)], last_frame_sec=0.9)[0]
    # the moment and the after frame both clamp to the last frame and are shown once
    assert [f.timestamp_sec for f in frames] == [0.0, 0.9]
