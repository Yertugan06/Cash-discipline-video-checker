"""Bounded, local-only state verification selected by F1 events.

``verify_video`` returns JSON-serializable evidence records with the shared keys
``family,t,box,answer,ok,source,question_id``. Additional fields describe the actual
trigger, prompt, frame time, inference/cache provenance, latency and failures.
``unknown`` is never a negative answer. Scene-start checks are observations, not
entries. Only door/laptop/safe states are implemented; no cash or ID inference.

Model imports and pixels stay in a local subprocess. It loads offline weights
lazily, takes the shared GPU flock, and can be terminated at the request deadline.
Importing this module (including through backend.main) does not import torch/PIL.
Cache identity covers video content, model files, prompt/schema, calibrated crop,
actual sample time, sampling/crop settings and implementation version. Failed
requests are not cached. No image bytes are written to traces or stdout.
"""

from __future__ import annotations

import atexit
import bisect
import hashlib
import json
import logging
import math
import os
import re
import selectors
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from dataclasses import replace as replace_request
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.f1.vision_types import Box, Event, Observation, Scene, State, center, contains

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.f1.events import EventLog

logger = logging.getLogger(__name__)
VERSION = 1
FAMILIES = ("door", "laptop", "safe")


class VisualCheckSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    enabled: bool = False
    model_path: Path | None = None
    worker_python: Path | None = None
    cache_dir: Path | None = None
    families: tuple[Literal["safe", "door", "laptop"], ...] = Field(default=("safe",), min_length=1)
    max_checks: int = Field(default=24, ge=0, le=96)
    max_video_s: float = Field(default=60, gt=0, le=270)
    # Measured cold start is ~40 s including process/model startup; warm checks ~0.5 s.
    request_timeout_s: float = Field(default=45, gt=0, le=120)
    stop_margin_s: float = Field(default=5, ge=0)
    crop_margin: float = Field(default=0.25, ge=0, le=0.5)
    max_side: int = Field(default=896, ge=64, le=1280)
    max_new_tokens: int = Field(default=64, ge=8, le=128)
    cpu_threads: int = Field(default=4, ge=1, le=16)
    gpu_lock: Path = Path.home() / ".cache/datathon-workers/gpu.lock"


# Adapted from forte_proto/brev_kit/scripts/zoom_checks.py CHECKS. Unknown is
# explicit; a dark screen is not proof of locking, nor a shut safe of its lock.
QUESTIONS = {
    "door": (
        "This is a zoomed crop of a glass room door. Is the door open (the leaf is "
        "swung away from the frame, a gap or opening is visible, or someone is passing "
        "through) or closed (the leaf is flush with its frame)? "
        'Return only JSON {"answer":"open"}, {"answer":"closed"}, or '
        '{"answer":"unknown"}. Use unknown if the door or frame is obscured or unclear. '
        "Do not infer whether the door is locked.",
        ("open", "closed", "unknown"),
    ),
    "laptop": (
        "This is a zoomed crop of a laptop. What does the screen show? "
        "working = a clearly visible application window (spreadsheet/table with rows, "
        "document, browser); locked = a clearly recognizable lock or login screen; "
        "closed = a visibly shut laptop lid. A dark, tiny, obscured, unreadable screen "
        "or wallpaper alone is unknown, not proof of locking or a closed lid. "
        'Return only JSON with one answer: {"answer":"working"}, {"answer":"locked"}, '
        '{"answer":"closed"}, or {"answer":"unknown"}.',
        ("working", "locked", "closed", "unknown"),
    ),
    "safe": (
        "This is a zoomed crop of a metal safe/cabinet. Is the safe door open or closed? "
        "Open requires a visible gap, swung door or visible safe interior; closed "
        "requires the door visibly shut against its frame. Use unknown if obscured, "
        "unclear or outside the crop. A closed door does not prove the lock is locked. "
        'Return only JSON {"answer":"open"}, {"answer":"closed"}, or '
        '{"answer":"unknown"}. Do not assess keys or the locking mechanism.',
        ("open", "closed", "unknown"),
    ),
}


def question_schema(family: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer"],
        "properties": {"answer": {"type": "string", "enum": list(QUESTIONS[family][1])}},
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _valid_box(box: Any) -> bool:
    return (
        isinstance(box, (list, tuple))
        and len(box) == 4
        and all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


@dataclass(frozen=True)
class CheckRequest:
    family: str
    t: float
    box: Box | None
    question_id: str
    trigger: str
    trigger_t: float
    observed_entry: bool = False
    actor_id: str = ""
    window_start: float | None = None
    window_end: float | None = None
    parent_trigger: str = ""


def plan_checks(
    scene: Scene,
    log: EventLog,
    observations: Sequence[Observation],
    duration: float,
    *,
    families: Sequence[str] = FAMILIES,
) -> list[CheckRequest]:
    """Select actual sampled times, without a filename, outcome or timestamp table.

    Three adjacent samples allow the existing event hysteresis to see a supported
    state change. No answers are propagated to unqueried frames. Samples beyond
    recording cutoff are omitted rather than clamped to a misleading final frame.
    Bootstrap checks never create or confirm ENTER. A safe departure is selected
    from visible cashier movement even when CLIP missed the safe-open state.
    """
    times = sorted({o.timestamp_sec for o in observations if o.timestamp_sec < duration})
    if not times:
        return []
    requests: dict[tuple[str, float], CheckRequest] = {}

    def add(family, anchor, offsets, trigger, observed_entry=False, actor_id=""):
        obj = scene.objects.get(family)
        box = obj.box if obj is not None and _valid_box(obj.box) else None
        for offset in offsets:
            target = anchor + offset
            if target < times[0] or target > times[-1] or target >= duration:
                continue
            i = bisect.bisect_left(times, target)
            sample = min(times[max(0, i - 1) : i + 1], key=lambda t: abs(t - target))
            # Do not bridge gaps in perception coverage.
            if abs(sample - target) > 0.251:
                continue
            key = (family, sample)
            request = CheckRequest(
                family,
                sample,
                box,
                f"a21.{family}.v{VERSION}",
                trigger,
                anchor,
                observed_entry,
                actor_id,
            )
            if key not in requests or requests[key].trigger == "scene_start":
                requests[key] = request

    for family in ("door", "safe"):
        add(family, times[0], (0, 0.5, 1), "scene_start")
    for event in log.events:
        t, facts = event.timestamp_sec, event.facts
        if event.type == "ENTER" and facts.get("observed_entry") is True and t > times[0]:
            add("door", t, (4, 4.5, 5), "observed_entry", True, str(facts.get("actor_id", "")))
        room_exit = event.type == "EXIT" and facts.get("role") == "cashier"
        if room_exit or event.type == "WORKSTATION_AWAY_START":
            for family in ("laptop", "safe") if room_exit else ("safe",):
                add(
                    family,
                    t,
                    (0, 0.5, 1),
                    event.type.lower(),
                    actor_id=str(facts.get("actor_id", "")),
                )
        if event.type == "SAFE_UNATTENDED_START":
            add("safe", t, (0, 0.5, 1, 4, 4.5, 5), "safe_unattended")

    safe = scene.objects.get("safe")
    was_near: dict[str, bool] = {}
    if safe and _valid_box(safe.box):
        for observation in sorted(observations, key=lambda o: o.timestamp_sec):
            for person in observation.detections:
                if person.label != "person" or person.role != "cashier":
                    continue
                near = contains(safe.box, center(person.box), scene.scaled_distance(0.08)) or any(
                    contains(safe.box, hand, scene.scaled_distance(0.05))
                    for hand in person.wrists()
                )
                if was_near.get(person.track_id) and not near:
                    add(
                        "safe",
                        observation.timestamp_sec,
                        (0, 0.5, 1, 4, 4.5, 5),
                        "safe_departure",
                        actor_id=person.track_id,
                    )
                was_near[person.track_id] = near
    return sorted(
        (request for request in requests.values() if request.family in families),
        key=lambda r: (r.t, r.family),
    )


def _safe_window(request: CheckRequest, observations: Sequence[Observation]) -> list[CheckRequest]:
    """Request real half-second samples around this departure; assert no state in gaps."""
    start, end = max(0, request.trigger_t - 0.5), request.trigger_t + 4.5
    times = sorted({o.timestamp_sec for o in observations})
    if not times:
        return []
    start, end = max(start, times[0]), min(end, times[-1])
    return [
        replace_request(
            request,
            t=t,
            trigger="safe_open_window",
            parent_trigger=request.trigger,
            window_start=start,
            window_end=end,
        )
        for t in times
        if start <= t <= end and abs(t * 2 - round(t * 2)) < 1e-6
    ]


@lru_cache(maxsize=4)
def worker_environment(python: str) -> dict:
    """Inspect the actual worker environment without importing its ML libraries."""
    if not Path(python).is_file() or not os.access(python, os.X_OK):
        raise ModelUnavailable("worker_python_unavailable")
    script = (
        "import importlib.metadata as m,json,sys\n"
        "result={'worker_python':sys.executable}\n"
        "for name in ('torch','transformers','accelerate'):\n"
        " try: result[name]=m.version(name)\n"
        " except m.PackageNotFoundError: result[name]='missing'\n"
        "print(json.dumps(result))\n"
    )
    try:
        result = subprocess.run(
            [python, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ModelUnavailable("worker_python_unavailable") from exc


def model_identity(path: Path | None, worker_python: Path | None = None) -> dict:
    """Local content/config identity; tensor bytes never enter diagnostics.

    Tensor size/mtime_ns invalidate a changed installation without hashing GBs
    for every video. Small config/tokenizer files are hashed as well.
    """
    if path is None or not path.is_dir():
        raise ModelUnavailable("local_weights_missing")
    path = path.resolve()
    files = []
    for p in sorted(path.iterdir()):
        if not p.is_file() or p.suffix not in {".json", ".safetensors", ".txt", ".jinja"}:
            continue
        stat = p.stat()
        content = hashlib.sha256(p.read_bytes()).hexdigest() if stat.st_size < 4_000_000 else None
        files.append([p.name, stat.st_size, stat.st_mtime_ns, content])
    if not (path / "config.json").is_file() or not any(
        p[0].endswith(".safetensors") for p in files
    ):
        raise ModelUnavailable("local_weights_incomplete")
    return {
        "backend": "local_qwen3_vl",
        "path": str(path),
        "files_sha256": _digest(files),
        **worker_environment(str(worker_python or sys.executable)),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


class ModelUnavailable(RuntimeError):
    """A local model cannot answer; never interpreted as a state."""

    def __init__(self, message: str, *, diagnostic: dict | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic


class LocalQwenBackend:
    """One lazy, reusable subprocess; no image network transport of any kind."""

    def __init__(self, options: VisualCheckSettings, *, lock_held: bool = False):
        self.options = options
        self.lock_held = lock_held  # diagnostic runner only, when its launcher owns flock
        self._process: subprocess.Popen | None = None
        self._identity: dict | None = None
        atexit.register(self.close)

    def identity(self) -> dict:
        identity = model_identity(self.options.model_path, self.options.worker_python)
        if self._identity is not None and self._identity != identity:
            self.close()
        self._identity = identity
        return identity

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None:
            process.kill()
        process.communicate()

    def ask(self, frame: Path, request: CheckRequest, deadline: float) -> str:
        if time.monotonic() >= deadline:
            raise TimeoutError("request_deadline")
        if self._process is None:
            self._process = subprocess.Popen(
                [
                    str(self.options.worker_python or sys.executable),
                    "-m",
                    "backend.f1.visual_checks",
                    "--worker",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        process = self._process
        payload = {
            "frame": str(frame.resolve()),
            "box": request.box,
            "prompt": QUESTIONS[request.family][0],
            "deadline": deadline,
            "options": self.options.model_dump(mode="json"),
            "lock_held": self.lock_held,
        }
        try:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    line = process.stdout.readline()
                    if not line:
                        raise ModelUnavailable("local_worker_exited")
                    if not line.startswith("A21_VISUAL_RESULT "):
                        continue
                    result = json.loads(line.removeprefix("A21_VISUAL_RESULT "))
                    if result.get("error"):
                        self.close()
                        raise ModelUnavailable(
                            result["error"],
                            diagnostic=result.get("diagnostic"),
                        )
                    return result["raw"]
        except (OSError, ValueError, KeyError) as exc:
            self.close()
            raise ModelUnavailable("local_worker_protocol_failure") from exc
        self.close()
        raise TimeoutError("request_deadline")


@lru_cache(maxsize=1)
def _backend(options_json: str) -> LocalQwenBackend:
    return LocalQwenBackend(VisualCheckSettings.model_validate_json(options_json))


def _parse_answer(raw: str, family: str) -> str:
    if not isinstance(raw, str) or len(raw) > 2000:
        raise ValueError("invalid_output")

    def unique_keys(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError("invalid_output")
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique_keys)
    except ValueError as exc:
        raise ValueError("invalid_output") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"answer"}
        or not isinstance(value["answer"], str)
        or value["answer"] not in QUESTIONS[family][1]
    ):
        raise ValueError("invalid_output")
    return value["answer"]


def cache_identity(
    checksum: str,
    identity: dict,
    request: CheckRequest,
    options: VisualCheckSettings,
    fps: float,
    frame_sha256: str,
) -> dict:
    return {
        "version": VERSION,
        "video_sha256": checksum,
        "model": identity,
        "request": asdict(request),
        "prompt": QUESTIONS[request.family][0],
        "schema": question_schema(request.family),
        "fps": fps,
        "frame_sha256": frame_sha256,
        "sampling": "f1_ffmpeg_fps_nearest_v1",
        "crop_margin": options.crop_margin,
        "max_side": options.max_side,
        "max_new_tokens": options.max_new_tokens,
        "resize": "PIL_LANCZOS",
        "do_sample": False,
    }


def _schedule_requests(requests: list[CheckRequest]) -> list[CheckRequest]:
    """Round-robin families and keep adjacent checks together under a small budget.

    Actual entries/exits and safe departures precede weaker workstation triggers
    and bootstrap references. Skipped groups remain explicit unknown records.
    """
    priority = {
        "observed_entry": 0,
        "exit": 0,
        "safe_departure": 0,
        "safe_unattended": 1,
        "workstation_away_start": 2,
        "scene_start": 3,
    }
    groups: dict[tuple, list[CheckRequest]] = {}
    for request in requests:
        key = (request.family, request.trigger, request.trigger_t, request.actor_id)
        groups.setdefault(key, []).append(request)
    families = {
        family: sorted(
            [group for key, group in groups.items() if key[0] == family],
            key=lambda group: (priority[group[0].trigger], group[0].trigger_t),
        )
        for family in FAMILIES
    }
    output = []
    while any(families.values()):
        for family in FAMILIES:
            if families[family]:
                output.extend(families[family].pop(0))
    return output


def verify_video(
    video: Path,
    scene: Scene,
    log: EventLog,
    observations: Sequence[Observation],
    *,
    options: VisualCheckSettings,
    deadline_monotonic: float,
    duration: float,
    video_sha256: str | None = None,
    frames: Sequence[Path] | None = None,
    fps: float = 2.0,
    backend: Any = None,
) -> list[dict]:
    """Plan and run checks, returning evidence including every skipped request.

    ``frames`` uses F1's existing 2-fps extraction; the standalone runner can omit
    it to decode only selected frames via local ffmpeg. Dependency injection is
    for CPU tests; a production backend always identifies the actual local model.
    Disabled mode performs no planning, decode, model/cache access or mutation.
    """
    if not options.enabled:
        return []
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("fps and duration must be finite and positive")
    if not math.isfinite(deadline_monotonic):
        raise ValueError("deadline must be finite")
    started = time.monotonic()
    deadline = min(deadline_monotonic - options.stop_margin_s, started + options.max_video_s)
    requests = _schedule_requests(
        plan_checks(scene, log, observations, duration, families=options.families)
    )
    model = backend or _backend(options.model_dump_json())
    identity, unavailable = None, None
    evidence = []
    attempts = 0
    checksum = video_sha256
    temporary = None
    checked = set()
    expanded = set()
    index = 0
    try:
        while index < len(requests):
            request = requests[index]
            index += 1
            checked.add((request.family, request.t))
            record = {
                **asdict(request),
                "answer": "unknown",
                "ok": False,
                "source": "local_qwen3_vl:unavailable",
                "inference_requested": False,
                "inference_ran": False,
                "cache_hit": False,
                "latency_s": 0.0,
                "applied": False,
                "diagnostic_only": request.family == "door",
                "elapsed_video_s": round(time.monotonic() - started, 4),
                "prompt_sha256": _digest(QUESTIONS[request.family][0]),
            }
            evidence.append(record)
            t0 = time.monotonic()
            if request.box is None:
                record["error"] = "missing_calibration"
                continue
            if t0 >= deadline:
                record["error"] = "video_deadline"
                continue
            if attempts >= options.max_checks:
                record["error"] = "check_budget_exhausted"
                continue
            if unavailable:
                record["error"] = unavailable
                continue
            try:
                if identity is None:
                    identity = model.identity()
                record["source"] = f"{identity['backend']}:{identity['files_sha256']}"
                record["model"] = identity
                if checksum is None:
                    with video.open("rb") as stream:
                        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
                if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
                    raise ValueError("invalid_video_checksum")
                request_deadline = min(deadline, time.monotonic() + options.request_timeout_s)
                if frames is not None:
                    frame_index = round(request.t * fps)
                    if (
                        frame_index < 0
                        or frame_index >= len(frames)
                        or abs(frame_index / fps - request.t) > 1e-6
                    ):
                        raise ValueError("sample_frame_missing")
                    frame = frames[frame_index]
                    if not frame.is_file():
                        raise ValueError("sample_frame_missing")
                else:
                    if temporary is None:
                        temporary = tempfile.TemporaryDirectory(prefix="f1-visual-")
                    frame = Path(temporary.name) / f"{request.t:.6f}.png"
                    if not frame.is_file():
                        _extract_sample(video, frame, request.t, fps, request_deadline)
                with frame.open("rb") as stream:
                    frame_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
                key_data = cache_identity(checksum, identity, request, options, fps, frame_sha256)
                key = _digest(key_data)
                record["cache_key"] = key
                cache = options.cache_dir / f"{key}.json" if options.cache_dir is not None else None
                if cache is not None and cache.is_file():
                    try:
                        cached = json.loads(cache.read_text(encoding="utf-8"))
                        answer = _parse_answer(cached["raw"], request.family)
                        if cached["identity"] != json.loads(json.dumps(key_data)):
                            raise ValueError("cache_identity_mismatch")
                        record.update(answer=answer, ok=True, cache_hit=True, raw=cached["raw"])
                        continue
                    except (OSError, ValueError, KeyError, TypeError):
                        record["cache_warning"] = "invalid_cache_entry"
                attempts += 1
                record["sample_t"] = request.t
                record["inference_requested"] = True
                raw = model.ask(frame, request, request_deadline)
                record["inference_ran"] = True
                if isinstance(raw, str) and len(raw) <= 2000:
                    record["raw"] = (
                        raw if "base64" not in raw else "[invalid non-state output omitted]"
                    )
                if time.monotonic() >= request_deadline:
                    raise TimeoutError("request_deadline")
                answer = _parse_answer(raw, request.family)
                record.update(answer=answer, ok=True, raw=raw)
                if cache is not None:
                    try:
                        cache.parent.mkdir(parents=True, exist_ok=True)
                        with tempfile.NamedTemporaryFile(
                            mode="w", dir=cache.parent, delete=False
                        ) as f:
                            json.dump({"identity": key_data, "raw": raw}, f)
                            partial = Path(f.name)
                        partial.replace(cache)
                    except OSError:
                        record["cache_warning"] = "cache_write_failed"
            except ModelUnavailable as exc:
                unavailable = str(exc)
                record["error"] = unavailable
                if exc.diagnostic and options.cache_dir is not None:
                    try:
                        path = options.cache_dir.parent / "visual_checks_errors.jsonl"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                        with os.fdopen(fd, "w", encoding="utf-8") as diagnostic_file:
                            os.fchmod(diagnostic_file.fileno(), 0o600)
                            diagnostic_file.write(
                                json.dumps(
                                    {
                                        "error": unavailable,
                                        "family": request.family,
                                        "t": request.t,
                                        "model": identity,
                                        "diagnostic": exc.diagnostic,
                                    }
                                )
                                + "\n"
                            )
                        record["diagnostic_file"] = str(path)
                    except OSError:
                        record["diagnostic_warning"] = "private_diagnostic_write_failed"
                logger.warning("F1 visual checks unavailable: %s", unavailable)
            except (TimeoutError, subprocess.TimeoutExpired):
                unavailable = "request_deadline"
                record["error"] = unavailable
            except ValueError as exc:
                reason = str(exc)
                record["error"] = (
                    reason
                    if reason
                    in {
                        "invalid_output",
                        "sample_frame_missing",
                        "invalid_video_checksum",
                    }
                    else "invalid_output_or_frame"
                )
            except (OSError, subprocess.SubprocessError):
                record["error"] = "frame_decode_or_io_failed"
            finally:
                record["latency_s"] = round(time.monotonic() - t0, 4)
                record["elapsed_video_s"] = round(time.monotonic() - started, 4)
                origin = (request.trigger, request.trigger_t, request.actor_id)
                if (
                    request.family == "safe"
                    and record["ok"]
                    and record["answer"] == "open"
                    and request.trigger not in {"scene_start", "safe_open_window"}
                    and origin not in expanded
                ):
                    expanded.add(origin)
                    followups = [
                        r
                        for r in _safe_window(request, observations)
                        if (r.family, r.t) not in checked
                    ]
                    keys = {(r.family, r.t) for r in followups}
                    requests[index:] = followups + [
                        r for r in requests[index:] if (r.family, r.t) not in keys
                    ]
    finally:
        if temporary is not None:
            temporary.cleanup()
    return evidence


def apply_checks(observations: Sequence[Observation], checks: list[dict]) -> list[Observation]:
    """Refine exact sampled states only; never manufacture detections or confidence.

    State score/margin are zero because a generative categorical answer supplies
    no calibrated numeric probability. The trace evidence carries its provenance.
    Conflicting confirmed answers become unknown, with an explicit diagnostic.
    """
    output = [o.model_copy(deep=True) for o in observations]
    by_time = {o.timestamp_sec: o for o in output}
    confirmed: dict[tuple[str, float], set[str]] = {}
    for check in checks:
        family, t, answer = check.get("family"), check.get("t"), check.get("answer")
        if (
            not isinstance(family, str)
            or family not in QUESTIONS
            or not isinstance(t, (int, float))
            or isinstance(t, bool)
            or not math.isfinite(t)
            or not isinstance(answer, str)
            or check.get("ok") is not True
            or check.get("diagnostic_only") is True
            or answer not in QUESTIONS[family][1]
            or answer == "unknown"
            or not _valid_box(check.get("box"))
            or t not in by_time
        ):
            continue
        confirmed.setdefault((family, t), set()).add(answer)
    for (family, t), values in confirmed.items():
        value = next(iter(values)) if len(values) == 1 else "unknown"
        by_time[t].states[family] = State(value=value, score=0, margin=0)
        for check in checks:
            if check.get("family") == family and check.get("t") == t:
                check["applied"] = (
                    len(values) == 1 and check.get("answer") == value and check.get("ok") is True
                )
                if len(values) != 1:
                    check["apply_warning"] = "conflicting_answers"
    return output


def add_verified_state_events(log: EventLog, checks: list[dict]) -> EventLog:
    """An exact-frame confirmation bypasses CLIP hysteresis, not missing frames."""
    points = {
        (check["family"], check["t"]): check for check in checks if check.get("applied") is True
    }

    def family(event):
        if event.type == "SCREEN":
            return "laptop"
        if "state" in event.facts:
            return next(
                (f for f in ("door", "safe") if event.type.startswith(f.upper() + "_")), None
            )
        return None

    events = [event for event in log.events if (family(event), event.timestamp_sec) not in points]
    for (name, t), check in points.items():
        answer = check["answer"]
        events.append(
            Event(
                timestamp_sec=t,
                type="SCREEN" if name == "laptop" else f"{name.upper()}_{answer.upper()}",
                facts={
                    "state": answer,
                    "box": list(check["box"]),
                    "visual_verified": True,
                    "source": check["source"],
                    "question_id": check["question_id"],
                },
            )
        )
    log.events = sorted(events, key=lambda event: event.timestamp_sec)
    return log


def _extract_sample(video: Path, frame: Path, t: float, fps: float, deadline: float) -> None:
    # Same fps filter as F1Detector; select its actual sample index, rather than
    # seeking to a different raw-video frame and calling it the same cache key.
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("request_deadline")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-xerror",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(video.resolve()),
        "-an",
        "-vf",
        f"fps={fps},select=eq(n\\,{round(t * fps)})",
        "-frames:v",
        "1",
        "-threads",
        "1",
        str(frame),
    ]
    subprocess.run(command, capture_output=True, check=True, timeout=remaining)
    if not frame.is_file():
        raise ValueError("sample_frame_missing")


def _error_diagnostic(exc: Exception, stage: str) -> dict:
    message = re.sub(r"data:image/[^\s\"']+", "[image omitted]", str(exc))
    message = re.sub(r"[A-Za-z0-9+/]{120,}={0,2}", "[encoded content omitted]", message)
    message = re.sub(
        r"(?i)\b(authorization|api[_-]?key|token|password)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        message,
    )
    return {
        "stage": stage,
        "type": type(exc).__name__,
        "message": message[:1500],
        "frames": [
            {"file": f.filename, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(exc.__traceback__)[-8:]
        ],
    }


def _worker_main() -> None:
    """Local process protocol. Only JSON answers/errors, never pixels, on stdout."""
    import fcntl

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    model, processor = None, None
    for line in sys.stdin:
        lock = None
        stage = "request"
        try:
            job = json.loads(line)
            options = VisualCheckSettings.model_validate(job["options"])
            deadline = job["deadline"]
            if not job["lock_held"]:
                options.gpu_lock.parent.mkdir(parents=True, exist_ok=True)
                lock = options.gpu_lock.open("a")
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("gpu_lock_deadline")
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            stage = "imports"
            import torch
            from PIL import Image
            from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

            if not torch.cuda.is_available():
                raise ModelUnavailable("cuda_unavailable")
            if model is None:
                torch.set_num_threads(options.cpu_threads)
                stage = "model_load"
                model = Qwen3VLForConditionalGeneration.from_pretrained(
                    str(options.model_path),
                    dtype=torch.bfloat16,
                    device_map="cuda",
                    attn_implementation="sdpa",
                    local_files_only=True,
                ).eval()
                stage = "processor_load"
                processor = AutoProcessor.from_pretrained(
                    str(options.model_path),
                    local_files_only=True,
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("model_load_deadline")
            stage = "crop"
            with Image.open(job["frame"]) as original:
                image = original.convert("RGB")
            x1, y1, x2, y2 = job["box"]
            dx, dy = (x2 - x1) * options.crop_margin, (y2 - y1) * options.crop_margin
            w, h = image.size
            crop = image.crop(
                (
                    math.floor(max(0, x1 - dx) * w),
                    math.floor(max(0, y1 - dy) * h),
                    math.ceil(min(1, x2 + dx) * w),
                    math.ceil(min(1, y2 + dy) * h),
                )
            )
            scale = options.max_side / max(crop.size)
            crop = crop.resize(
                (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
                Image.Resampling.LANCZOS,
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": job["prompt"]},
                    ],
                }
            ]
            stage = "processor_inputs"
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = processor(text=[text], images=[crop], return_tensors="pt").to(model.device)
            inputs.pop("token_type_ids", None)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("request_deadline")
            stage = "generate"
            with torch.inference_mode():
                result = model.generate(
                    **inputs,
                    max_new_tokens=options.max_new_tokens,
                    do_sample=False,
                    max_time=remaining,
                )
            stage = "decode"
            raw = processor.batch_decode(
                result[:, inputs["input_ids"].shape[1] :],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0].strip()
            response = {"raw": raw}
        except Exception as exc:  # process boundary; sanitized details go to a private file
            response = {
                "error": str(exc)
                if isinstance(exc, (ModelUnavailable, TimeoutError))
                else f"local_inference_failed:{type(exc).__name__}",
                "diagnostic": _error_diagnostic(exc, stage),
            }
        finally:
            if lock is not None:
                lock.close()
        print("A21_VISUAL_RESULT " + json.dumps(response), flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use the A21 runner; this module's CLI is the local model worker.")
    _worker_main()
