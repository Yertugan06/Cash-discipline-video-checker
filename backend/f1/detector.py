"""F1Detector: the OWLv2 / CLIP / RTMPose / ByteTrack stack behind `Detector`.

This is the fallback (`DETECTOR=f1`, architecture.md §1 L3). It samples the
whole video uniformly at `FPS` (2 fps / 0.5 s step) rather than following
`SamplingPlan`'s coarse-then-fill grid -- the plan's `deadline_monotonic` is
still honoured, but `coarse_t`/`fill_t` are a VLM-sampler concept.

Only when 2 fps would not fit the job's time (other jobs queued, a long
video) does one job sample every 2nd or 4th frame (`sampling_stride`), with a
warning; the cost per frame is measured on this host's cold runs. If the
deadline still arrives mid-video, the seen prefix is evaluated as a recording
that ends there and coverage is `mode="partial", deadline_hit=True`.

Heavy imports (torch, onnxruntime, opencv, supervision, transformers) only
happen inside `detect()`, through the already-lazy `backend.f1.perception`
module, so importing this module -- and therefore `backend.main` -- never
pulls in torch.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.contracts import (
    Coverage,
    DetectionResult,
    EvidenceBox,
    Finding,
    RuleEntry,
    SamplingPlan,
    VideoInfo,
)

logger = logging.getLogger(__name__)

FPS = 2.0
STEP_S = 1.0 / FPS
_MAX_SUPPORT_SAMPLES = 8
# Every 1st, 2nd or 4th 2-fps frame: 2, 1 or 0.5 fps. Estimates are inflated by _COST_SAFETY.
STRIDES = (1, 2, 4)
_COST_SAFETY = 1.25


class F1DetectorError(RuntimeError):
    """The F1 stack could not produce a result for this video."""


def models_loadable(settings: Settings) -> bool:
    """Cheap readiness check: weights present and matching models.lock.json.

    Does not load torch or run inference; safe to call from `/readyz`.
    """
    from backend.f1.perception import verify_weights

    try:
        verify_weights(settings.weights_dir)
        return True
    except (ValueError, OSError):
        return False


def sampling_stride(frame_count: int, available_s: float, sec_per_frame: float) -> int:
    """The smallest stride whose estimated perception time fits `available_s`."""
    for stride in STRIDES:
        if math.ceil(frame_count / stride) * sec_per_frame * _COST_SAFETY <= available_s:
            return stride
    return STRIDES[-1]


class F1Detector:
    """`Detector` implementation wrapping the existing F1 CV stack.

    `rules` is the Knowledge Pack's rule list (same shape `VlmDetector` takes):
    startup validates that configured evaluator IDs and Knowledge Pack lifecycle
    metadata agree. Only enabled rules are passed to the evaluator, so there is
    no post-detection allowlist filter that can silently remove findings.
    """

    def __init__(self, settings: Settings, rules: list[RuleEntry]) -> None:
        from backend.f1.codex import load_codex
        from backend.f1.rules import RULES as EVALUATORS

        self._settings = settings
        self._sec_per_frame = settings.f1_sec_per_frame
        self._codex = load_codex(settings.f1_codex_path)
        self._rules_by_id = {r.rule_id: r for r in rules}
        codex_by_id = {rule.id: rule for rule in self._codex.rules}
        errors: list[str] = []
        if set(codex_by_id) != set(self._rules_by_id):
            errors.append(
                "F1 codex and Knowledge Pack rule IDs differ: "
                f"codex-only={sorted(set(codex_by_id) - set(self._rules_by_id))}, "
                f"knowledge-only={sorted(set(self._rules_by_id) - set(codex_by_id))}"
            )
        implemented_ids = {
            rule_id
            for rule_id, rule in self._rules_by_id.items()
            if rule.implementation_status == "implemented"
        }
        evaluator_ids = set(EVALUATORS)
        if evaluator_ids != implemented_ids:
            errors.append(
                "F1 evaluator IDs do not match implementation_status: "
                f"evaluator-only={sorted(evaluator_ids - implemented_ids)}, "
                f"pack-only={sorted(implemented_ids - evaluator_ids)}"
            )
        for rule_id, rule in self._rules_by_id.items():
            source = codex_by_id.get(rule_id)
            if source is None:
                continue
            codex_status = source.status.lower()
            if codex_status != rule.business_status:
                errors.append(
                    f"{rule_id} business_status={rule.business_status!r} "
                    f"does not match F1 codex status={source.status!r}"
                )
            if rule.enabled and rule_id not in EVALUATORS:
                errors.append(f"enabled rule {rule_id} has no F1 evaluator")
        if errors:
            raise ValueError("Invalid rule configuration: " + "; ".join(errors))

    def detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult:
        from backend.f1.calibration import video_checksum
        from backend.f1.events import build_events
        from backend.f1.perception import perceive_video
        from backend.f1.rules import Context, evaluate_rules

        settings = self._settings
        deadline = plan.deadline_monotonic
        frames_dir = Path(tempfile.mkdtemp(prefix="f1-frames-", dir=str(settings.work_dir)))
        try:
            all_frames = self._extract_frames(video, frames_dir, deadline)
            if not all_frames:
                raise F1DetectorError("No video frames could be decoded")
            checksum = video_checksum(video)
            stride = sampling_stride(
                len(all_frames), deadline - time.monotonic(), self._sec_per_frame
            )
            frames = all_frames[::stride]
            fps = FPS / stride
            try:
                scene, observations, config = perceive_video(
                    frames, checksum, settings, deadline, fps
                )
            except TimeoutError as exc:
                raise F1DetectorError("Processing exceeded the configured time limit") from exc
            except (ValueError, OSError, RuntimeError) as exc:
                # Library/OS messages can hold paths and internals: log them, show a fixed message.
                logger.warning("F1 perception failed: %s", exc)
                raise F1DetectorError("F1 perception failed on this video") from exc
            if not config["cache_hit"] and len(observations) >= 10:
                measured = config["loop_s"] / len(observations)
                self._sec_per_frame = (self._sec_per_frame + measured) / 2
            complete = config["complete"]
            # A cut-off run is evaluated as a recording that ends after its last sample.
            covered_s = (
                info.duration_sec
                if complete
                else min(info.duration_sec, observations[-1].timestamp_sec + 1 / fps)
            )
            # Frames that have an observation; a complete run must still match them one to one.
            seen_frames = frames if complete else frames[: len(observations)]
            sampling_warnings = _sampling_warnings(fps, complete, covered_s, info.duration_sec)
            for warning in sampling_warnings:
                logger.warning("%s", warning)
            log = build_events(scene, observations, config, fps, covered_s)
            checks = None
            visual_warnings: list[str] = []
            if settings.visual_checks.enabled:
                from backend.f1.visual_checks import (
                    add_verified_state_events,
                    apply_checks,
                    verify_video,
                )

                check_options = settings.visual_checks
                if check_options.cache_dir is None:
                    check_options = check_options.model_copy(
                        update={"cache_dir": settings.work_dir / "visual_checks_cache"}
                    )
                checks = verify_video(
                    video,
                    scene,
                    log,
                    observations,
                    options=check_options,
                    deadline_monotonic=deadline,
                    duration=covered_s,
                    video_sha256=checksum,
                    frames=seen_frames,
                    fps=fps,
                )
                observations = apply_checks(observations, checks)
                log = build_events(scene, observations, config, fps, covered_s)
                log = add_verified_state_events(log, checks)
                unknown = sum(check["answer"] == "unknown" for check in checks)
                errors = sorted({check["error"] for check in checks if check.get("error")})
                if unknown:
                    visual_warnings.append(
                        f"Visual verification: {unknown}/{len(checks)} checks unknown"
                        + (f" ({', '.join(errors)})" if errors else " (model uncertain)")
                        + "; unknown does not establish an object state."
                    )
                for warning in visual_warnings:
                    logger.warning("%s", warning)
            desk_objects = None
            if config.get("desk_objects", False):
                from backend.f1.desk_objects import build_desk_objects

                if len(seen_frames) != len(observations):
                    raise F1DetectorError(
                        "Desk history frames do not match perception observations"
                    )
                try:
                    desk_objects = build_desk_objects(
                        _desk_images(seen_frames, deadline), observations, scene, log
                    )
                except F1DetectorError:
                    raise
                except (ValueError, OSError, RuntimeError) as exc:
                    logger.warning("Desk object history failed: %s", exc)
                    raise F1DetectorError("Desk object history failed on this video") from exc
                if time.monotonic() > deadline:
                    raise F1DetectorError("Processing exceeded the configured time limit")
            context = Context(
                self._codex,
                log,
                observations,
                scene,
                covered_s,
                desk_objects,
                visual_checks=checks,
            )
            enabled_ids = {rule_id for rule_id, rule in self._rules_by_id.items() if rule.enabled}
            legacy_findings = evaluate_rules(context, enabled_ids)
            findings = [self._to_finding(f, info.duration_sec) for f in legacy_findings]
            trace = build_trace(
                checksum, config, info.duration_sec, scene, observations, log, fps=fps
            )
            trace["sampling"] = {"stride": stride, "complete": complete, "covered_s": covered_s}
            if checks is not None:
                trace["visual_checks"] = checks
                trace["warnings"].extend(visual_warnings)
            trace["findings"] = [{**vars(f), "kept": True} for f in legacy_findings]
            trace["desk_objects_enabled"] = config.get("desk_objects", False)
            trace["desk_objects"] = (
                [{**asdict(obj), "track_id": obj.track_id} for obj in desk_objects]
                if desk_objects is not None
                else None
            )
            write_trace(settings.traces_dir / f"{video.stem}.json", trace)
            coverage = Coverage(
                step_s=1 / fps,
                planned=len(frames),
                done=len(observations),
                failed=0,
                deadline_hit=not complete or time.monotonic() > deadline,
                mode="full" if complete else "partial",
            )
            return DetectionResult(
                findings=findings,
                coverage=coverage,
                warnings=[*scene.warnings, *sampling_warnings, *visual_warnings],
            )
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)

    @staticmethod
    def _extract_frames(video: Path, out_dir: Path, deadline: float) -> list[Path]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise F1DetectorError("Processing exceeded the configured time limit")
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
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"fps={FPS}",
            "-q:v",
            "3",
            str(out_dir / "%06d.jpg"),
        ]
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
            raise F1DetectorError("Required local executable is missing: ffmpeg") from exc
        except subprocess.TimeoutExpired as exc:
            raise F1DetectorError("Processing exceeded the configured time limit") from exc
        if process.returncode:
            logger.warning("ffmpeg frame decoding failed: %s", process.stderr[-800:].strip())
            raise F1DetectorError("The video could not be decoded")
        return sorted(out_dir.glob("*.jpg"))

    def _to_finding(self, legacy: Any, duration_sec: float) -> Finding:
        t_anchor = min(max(0.0, float(legacy.timestamp_sec)), duration_sec)
        t_end = t_anchor
        duration = legacy.facts.get("duration_sec")
        window_end = legacy.facts.get("window_end")
        if isinstance(duration, int | float) and duration > 0:
            t_end = t_anchor + float(duration)
        elif isinstance(window_end, int | float) and window_end > t_anchor:
            t_end = float(window_end)
        t_end = min(t_end, duration_sec)

        # knowledge/rules.yaml's description templates are written for
        # backend.rules.timeline's fact shape; add the keys they expect that
        # the legacy F1 facts do not carry under the same names.
        facts = _scalar_facts(legacy.facts)
        facts["t_start"] = round(t_anchor, 1)
        facts["t_end"] = round(t_end, 1)
        rule = self._rules_by_id.get(legacy.rule_id)
        if rule is not None:
            facts.update(_extra_template_facts(legacy.rule_id, legacy.facts, rule))

        return Finding(
            rule_id=legacy.rule_id,
            t_anchor=t_anchor,
            t_start=t_anchor,
            t_end=t_end,
            support_t=_support_times(t_anchor, t_end),
            facts=facts,
            rank_score=max(
                0.0,
                min(1.0, float(legacy.confidence if legacy.confidence is not None else 1.0)),
            ),
            detection_confidence=(
                max(0.0, min(1.0, float(legacy.confidence)))
                if legacy.confidence is not None
                else None
            ),
            boxes=_evidence_boxes(legacy.facts),
        )


def _sampling_warnings(
    fps: float, complete: bool, covered_s: float, duration_s: float
) -> list[str]:
    warnings = []
    if fps < FPS:
        warnings.append(
            f"Sampling reduced to {fps:g} fps (normally {FPS:g}) to fit the time limit; "
            "short events can be missed and timecodes are less precise."
        )
    if not complete:
        warnings.append(
            f"Time limit reached: only {_mmss(covered_s)} of {_mmss(duration_s)} was analysed; "
            "the rest of the video was not checked."
        )
    return warnings


def _mmss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _desk_images(frames: list[Path], deadline: float) -> Iterator[Any]:
    import cv2

    for frame in frames:
        if time.monotonic() > deadline:
            raise F1DetectorError("Processing exceeded the configured time limit")
        image = cv2.imread(str(frame))
        if image is None:
            raise F1DetectorError("A video frame could not be decoded for desk object history")
        yield image


def build_trace(
    checksum: str,
    config: dict,
    duration: float,
    scene: Any,
    observations: list,
    log: Any,
    fps: float = FPS,
) -> dict[str, Any]:
    """Everything between perception and findings, for debugging a verdict and for the
    replay overlay: calibration, raw state changes, the event log and per-frame boxes
    (person boxes carry the role the event builder gave them, "glass" when ignored)."""
    changes, last = [], {}
    for observation in observations:
        for key, state in observation.states.items():
            if last.get(key) != state.value:
                last[key] = state.value
                changes.append(
                    {
                        "t": observation.timestamp_sec,
                        "key": key,
                        "value": state.value,
                        "score": round(state.score, 3),
                        "margin": round(state.margin, 3),
                    }
                )
    return {
        "video_sha256": checksum,
        "perception_cache_hit": bool(config.get("cache_hit")),
        "fps": fps,
        "duration_sec": duration,
        "scene": scene.model_dump(),
        "state_changes": changes,
        "events": [event.model_dump() for event in log.events],
        "coverage": log.coverage,
        "sessions": log.sessions,
        "warnings": log.warnings,
        "frames": [
            {
                "t": observation.timestamp_sec,
                "dets": [
                    [d.label, d.track_id, d.role, *(round(v, 4) for v in d.box), round(d.score, 3)]
                    for d in observation.detections
                ],
            }
            for observation in observations
        ],
    }


def write_trace(path: Path, trace: dict[str, Any]) -> None:
    """Diagnostics only: a failed write is logged, never fails the job."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        partial.write_text(json.dumps(trace, ensure_ascii=False, default=str), encoding="utf-8")
        partial.replace(path)
    except OSError:
        logger.exception("Could not write trace %s", path)


def _scalar_facts(facts: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Narrow legacy facts (which may include lists of track ids) to contract-safe scalars."""
    result: dict[str, str | int | float | bool] = {}
    for key, value in facts.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            result[key] = value
        elif isinstance(value, list | tuple | set):
            result[key] = ",".join(str(item) for item in value)
        else:
            result[key] = str(value)
    return result


def _evidence_boxes(facts: dict[str, Any]) -> list[EvidenceBox]:
    """The legacy events record the triggering object's normalized box under
    `box` (an empty list when the scene object was never localized); label it
    with the object class, else the actor's role, else the track id."""
    box = facts.get("box")
    if not isinstance(box, list | tuple) or len(box) != 4:
        return []
    x1, y1, x2, y2 = (min(max(float(value), 0.0), 1.0) for value in box)
    if x2 <= x1 or y2 <= y1:
        return []
    label = facts.get("object") or facts.get("role") or facts.get("track_id") or "object"
    return [EvidenceBox(label=str(label), box=(x1, y1, x2, y2))]


def _extra_template_facts(
    rule_id: str, legacy_facts: dict[str, Any], rule: RuleEntry
) -> dict[str, str | int | float | bool]:
    """Rule-specific slots that `rule.description_template` needs beyond the
    generic `t`/`t_start`/`t_end` (see knowledge/rules.yaml). Kept as an
    explicit, documented adapter rather than a generic heuristic, since each
    is a one-off translation from the legacy F1 facts to a display value."""
    if rule_id == "L-NO-CASH-ON-LEAVE":
        labels = {str(tid).split(":", 1)[0] for tid in legacy_facts.get("track_ids", [])}
        label_ru = {"cash": "наличные", "bundle": "пачка наличных", "bag": "сумка с ценностями"}
        translated = sorted(label_ru.get(label, label) for label in labels)
        return {"object": "/".join(translated) or "наличные"}
    if rule_id == "A-OUTSIDER-ZONE":
        # The legacy event does not count simultaneous occupants; one outsider
        # is what triggered the rule, so 1 is the honest minimum, not an
        # invented precise count.
        return {"people_count": 1}
    if rule_id == "K-SEAL-CHECK":
        return {"collector_quick_s": rule.params.get("collector_quick_s", 0.0)}
    return {}


def _support_times(t_start: float, t_end: float) -> list[float]:
    if t_end <= t_start:
        return [round(t_start, 3)]
    count = min(_MAX_SUPPORT_SAMPLES - 1, max(1, round((t_end - t_start) / STEP_S)))
    step = (t_end - t_start) / count
    return sorted({round(t_start + i * step, 3) for i in range(count + 1)})
