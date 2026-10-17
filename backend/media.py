"""Video probing and single-frame JPEG extraction via ffprobe/ffmpeg.

Both the evidence builder (WP1) and the VLM sampler (WP2) extract frames
through `extract_jpeg`; it is the one place that shells out to ffmpeg for a
single frame. No other module should call ffmpeg directly for this purpose.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from backend.contracts import VideoInfo

MAX_DURATION_SEC = 180.0

logger = logging.getLogger(__name__)


class MediaError(ValueError):
    """The video cannot be read, has no video stream, or is too long."""


def _run(command: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaError(f"Required local executable is missing: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Media probing exceeded its time limit") from exc


def probe(video: Path) -> VideoInfo:
    """Read duration, resolution and frame rate with ffprobe.

    Raises `MediaError` if the file is unreadable, has no video stream, or
    the duration exceeds `MAX_DURATION_SEC`.
    """
    process = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,duration:format=duration",
            "-of",
            "json",
            str(video.resolve()),
        ]
    )
    if process.returncode:
        # ffmpeg stderr holds server paths and build details: log it, show a fixed message.
        logger.warning("ffprobe failed: %s", process.stderr.decode(errors="replace")[-800:].strip())
        raise MediaError("The video could not be read (unsupported or corrupt file)")
    try:
        payload = json.loads(process.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        duration_raw = stream.get("duration") or payload["format"]["duration"]
        duration = float(duration_raw)
        num, _, den = str(stream.get("r_frame_rate", "0/1")).partition("/")
        fps = float(num) / float(den) if den and float(den) else float(num or 0.0)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise MediaError("Video has no valid video stream or duration") from exc
    if duration <= 0 or duration > MAX_DURATION_SEC:
        raise MediaError(f"Video duration {duration:g}s is outside (0, {MAX_DURATION_SEC:g}] s")
    if width <= 0 or height <= 0 or fps <= 0:
        raise MediaError("Video stream has invalid resolution or frame rate")
    sha256 = _sha256(video)
    return VideoInfo(sha256=sha256, duration_sec=duration, width=width, height=height, fps=fps)


def _sha256(path: Path) -> str:
    import hashlib

    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_jpeg(video: Path, t: float, max_side: int | None = None, quality: int = 90) -> bytes:
    """Seek to `t` seconds and return one JPEG frame as bytes.

    Raises `MediaError` if ffmpeg cannot decode a frame at that time.
    """
    if t < 0:
        raise MediaError("Frame timestamp must be non-negative")
    filters = []
    if max_side is not None:
        filters.append(
            f"scale='if(gt(iw,ih),min(iw,{max_side}),-2)':'if(gt(iw,ih),-2,min(ih,{max_side}))'"
        )
    quality_scale = max(2, min(31, round(31 - (quality / 100) * 29)))
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        f"{max(t, 0.0):.3f}",
        "-i",
        str(video.resolve()),
        "-frames:v",
        "1",
        "-an",
    ]
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-q:v", str(quality_scale), "-f", "mjpeg", "pipe:1"]
    process = _run(command, timeout=30.0)
    if process.returncode or not process.stdout:
        logger.warning(
            "ffmpeg frame extraction at %gs failed: %s",
            t,
            process.stderr.decode(errors="replace")[-800:].strip(),
        )
        raise MediaError(f"Could not extract a frame at {t:g}s")
    return process.stdout
