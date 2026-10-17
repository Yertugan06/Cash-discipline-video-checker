"""F1Detector: the OWLv2 / CLIP / RTMPose / ByteTrack stack behind `Detector`.

This is the fallback (`DETECTOR=f1`, architecture.md §1 L3). It samples the
whole video uniformly at `FPS` (2 fps / 0.5 s step) rather than following
`SamplingPlan`'s coarse-then-fill grid -- the plan's `deadline_monotonic` is
still honoured, but `coarse_t`/`fill_t` are a VLM-sampler concept. Coverage
is always reported as `mode="full", step_s=0.5` (or `deadline_hit=True` if
the budget ran out before perception finished).

Heavy imports (torch, onnxruntime, opencv, supervision, transformers) only
happen inside `detect()`, through the already-lazy `backend.f1.perception`
module, so importing this module -- and therefore `backend.main` -- never
pulls in torch.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.contracts import Coverage, DetectionResult, Finding, RuleEntry, SamplingPlan, VideoInfo

FPS = 2.0
STEP_S = 1.0 / FPS
_MAX_SUPPORT_SAMPLES = 8

logger = logging.getLogger(__name__)


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


class F1Detector:
    """`Detector` implementation wrapping the existing F1 CV stack.

    `rules` is the Knowledge Pack's rule list (same shape `VlmDetector` takes):
    the F1 engine's own rule functions cover a slightly wider mechanism set
    than the canonical knowledge pack (e.g. the legacy `L-NO-BAG-ON-LEAVE`
    and `K-COLLECTOR-DOC` are not canonical ids -- see knowledge/rules.yaml),
    so findings for any rule_id not in `rules` are dropped before returning.
    """

    def __init__(self, settings: Settings, rules: list[RuleEntry]) -> None:
        from backend.f1.codex import load_codex

        self._settings = settings
        self._codex = load_codex(settings.f1_codex_path)
        self._rules_by_id = {r.rule_id: r for r in rules}

    def detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult:
        from backend.f1.calibration import video_checksum
        from backend.f1.events import build_events
        from backend.f1.perception import perceive_video
        from backend.f1.rules import Context, evaluate_rules

        settings = self._settings
        deadline = plan.deadline_monotonic
        frames_dir = Path(tempfile.mkdtemp(prefix="f1-frames-", dir=str(settings.work_dir)))
        try:
            frames = self._extract_frames(video, frames_dir, deadline)
            if not frames:
                raise F1DetectorError("No video frames could be decoded")
            checksum = video_checksum(video)
            try:
                scene, observations, config = perceive_video(
                    frames, checksum, settings, deadline, FPS
                )
            except TimeoutError as exc:
                raise F1DetectorError("Processing exceeded the configured time limit") from exc
            except (ValueError, OSError, RuntimeError) as exc:
                # Library/OS messages can hold paths and internals: log them, show a fixed message.
                logger.warning("F1 perception failed: %s", exc)
                raise F1DetectorError("F1 perception failed on this video") from exc
            log = build_events(scene, observations, config, FPS, info.duration_sec)
            context = Context(self._codex, log, observations, scene, info.duration_sec)
            legacy_findings = evaluate_rules(context)
            findings = [
                self._to_finding(f, info.duration_sec)
                for f in legacy_findings
                if f.rule_id in self._rules_by_id
            ]
            planned = len(frames)
            coverage = Coverage(
                step_s=STEP_S,
                planned=planned,
                done=planned,
                failed=0,
                deadline_hit=time.monotonic() > deadline,
                mode="full",
            )
            return DetectionResult(
                findings=findings, coverage=coverage, warnings=list(scene.warnings)
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
            rank_score=max(0.0, min(1.0, float(legacy.confidence))),
        )


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


def _extra_template_facts(
    rule_id: str, legacy_facts: dict[str, Any], rule: RuleEntry
) -> dict[str, str | int | float | bool]:
    """Rule-specific slots that `rule.description_template` needs beyond the
    generic `t`/`t_start`/`t_end` (see knowledge/rules.yaml). Kept as an
    explicit, documented adapter rather than a generic heuristic, since each
    is a one-off translation from the legacy F1 facts to a display value."""
    if rule_id == "L-NO-CASH-ON-LEAVE":
        labels = {str(tid).split(":", 1)[0] for tid in legacy_facts.get("track_ids", [])}
        label_ru = {"cash": "наличные", "bundle": "пачка наличных"}
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
