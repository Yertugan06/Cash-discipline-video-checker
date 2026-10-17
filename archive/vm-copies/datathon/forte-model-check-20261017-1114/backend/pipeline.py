"""The single local inference pipeline used by the worker and the evaluator."""

import json
import shutil
import subprocess
import time
from pathlib import Path

from backend.codex import load_codex
from backend.config import Settings
from backend.models import AnalysisResult, Event, VideoMetadata


class AnalysisError(Exception):
    """A video could not be processed; never substitute a clean verdict."""


def run_media(command: list[str], deadline: float) -> str:
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise AnalysisError("Processing exceeded the configured time limit")
    try:
        process = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=remaining,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AnalysisError(f"Required local executable is missing: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AnalysisError("Processing exceeded the configured time limit") from exc
    if process.returncode:
        raise AnalysisError(f"{command[0]} rejected the video: {process.stderr[-800:].strip()}")
    return process.stdout


def analyze_video(
    video_path: Path, output_dir: Path, settings: Settings, *, debug: bool = False
) -> AnalysisResult:
    started = time.perf_counter()
    deadline = started + settings.timeout_sec
    codex = load_codex(settings.codex_path)
    if video_path.suffix.lower() != ".mov" or not video_path.is_file():
        raise AnalysisError("A local .mov file is required")
    probe = json.loads(
        run_media(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                "mov",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of",
                "json",
                str(video_path.resolve()),
            ],
            deadline,
        )
    )
    try:
        stream = probe["streams"][0]
        duration = float(stream.get("duration") or probe["format"]["duration"])
        metadata = VideoMetadata(
            duration_sec=duration,
            width=stream["width"],
            height=stream["height"],
            sample_fps=settings.sample_fps,
            sampled_frames=1,
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AnalysisError("Video has no valid video stream or duration") from exc
    if metadata.duration_sec > settings.max_duration_sec:
        raise AnalysisError(f"Video exceeds {settings.max_duration_sec:g} seconds")
    if metadata.width * metadata.height > 4096 * 4096:
        raise AnalysisError("Video resolution exceeds 4096 × 4096 pixels")
    samples = output_dir / "samples"
    samples.mkdir(parents=True, exist_ok=False)
    run_media(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-xerror",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "mov",
            "-threads",
            "2",
            "-i",
            str(video_path.resolve()),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"fps={settings.sample_fps}:start_time=0",
            "-q:v",
            "3",
            "-threads",
            "2",
            str(samples.resolve() / "%06d.jpg"),
        ],
        deadline,
    )
    frames = sorted(samples.glob("*.jpg"))
    if not frames:
        raise AnalysisError("No video frames could be decoded")
    metadata.sampled_frames = len(frames)
    from backend.calibration import video_checksum
    from backend.events import build_events
    from backend.evidence import build_violations, render_debug
    from backend.perception import perceive_video
    from backend.rules import Context, evaluate_rules

    try:
        scene, observations, config = perceive_video(
            frames, video_checksum(video_path), settings, deadline
        )
    except (ValueError, TimeoutError, OSError, RuntimeError) as exc:
        raise AnalysisError(str(exc)) from exc
    log = build_events(scene, observations, config, settings.sample_fps, duration)
    context = Context(codex, log, observations, scene, duration)
    findings = evaluate_rules(context)
    violations = build_violations(
        findings, codex, frames, observations, scene, settings.sample_fps, output_dir
    )
    events = [
        Event(timestamp_sec=0, type="DECODE_STARTED"),
        Event(
            timestamp_sec=0,
            type="CALIBRATED",
            facts={"confidence": scene.confidence, "objects": list(scene.objects)},
        ),
    ] + log.events
    events.append(Event(timestamp_sec=duration, type="DECODE_COMPLETED"))
    events.sort(key=lambda event: event.timestamp_sec)
    (output_dir / "perception.json").write_text(
        json.dumps(
            {
                "scene": scene.model_dump(),
                "observations": [o.model_dump() for o in observations],
                "config": config,
                "fps": settings.sample_fps,
            }
        ),
        encoding="utf-8",
    )
    if debug:
        debug_frames = output_dir / "debug_frames"
        render_debug(frames, observations, scene, debug_frames)
        run_media(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-framerate",
                str(settings.sample_fps),
                "-i",
                str(debug_frames.resolve() / "%06d.jpg"),
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-threads",
                "2",
                "-preset",
                "ultrafast",
                "-crf",
                "25",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-y",
                str((output_dir / "debug.mp4").resolve()),
            ],
            deadline,
        )
        shutil.rmtree(debug_frames)
    if time.perf_counter() > deadline:
        raise AnalysisError("Processing exceeded the configured time limit")
    result = AnalysisResult(
        verdict="violation" if violations else "no_violation",
        violations=violations,
        warnings=log.warnings,
        runtime_sec=time.perf_counter() - started,
        video=metadata,
        events=events,
        debug_available=debug,
        coverage=log.coverage,
        perception_cached=bool(config.get("cache_hit", False)),
    )
    (output_dir / "analysis.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    shutil.rmtree(samples)
    return result
