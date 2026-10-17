"""Tests for `backend.media.probe` / `extract_jpeg`. Needs real ffmpeg/ffprobe
(SHARED_BRIEF.md: skip, don't fake, when they are not installed)."""

from __future__ import annotations

import pytest

from backend.media import MediaError, extract_jpeg, probe
from tests.conftest import make_video, requires_ffmpeg


@requires_ffmpeg
def test_probe_reads_duration_resolution_and_fps(tmp_path):
    video = make_video(tmp_path / "a.mov", duration=2.0, width=64, height=96)
    info = probe(video)
    assert 1.5 <= info.duration_sec <= 2.5
    assert info.width == 64 and info.height == 96
    assert info.fps > 0
    assert len(info.sha256) == 64


@requires_ffmpeg
def test_probe_rejects_a_missing_or_corrupt_file(tmp_path):
    bad = tmp_path / "bad.mov"
    bad.write_bytes(b"not a video")
    with pytest.raises(MediaError):
        probe(bad)
    with pytest.raises(MediaError):
        probe(tmp_path / "missing.mov")


@requires_ffmpeg
def test_extract_jpeg_returns_real_jpeg_bytes(tmp_path):
    video = make_video(tmp_path / "b.mov", duration=2.0)
    jpeg = extract_jpeg(video, 0.5)
    assert jpeg.startswith(b"\xff\xd8")
    assert jpeg.rstrip(b"\x00").endswith(b"\xff\xd9") or jpeg.endswith(b"\xff\xd9")


@requires_ffmpeg
def test_extract_jpeg_can_downscale_to_max_side(tmp_path):
    import io

    from PIL import Image

    video = make_video(tmp_path / "c.mov", duration=1.0, width=640, height=480)
    jpeg = extract_jpeg(video, 0.1, max_side=100)
    image = Image.open(io.BytesIO(jpeg))
    assert max(image.size) <= 100


@requires_ffmpeg
def test_extract_jpeg_rejects_a_negative_timestamp(tmp_path):
    video = make_video(tmp_path / "d.mov", duration=1.0)
    with pytest.raises(MediaError):
        extract_jpeg(video, -1.0)
