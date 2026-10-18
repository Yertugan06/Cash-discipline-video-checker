"""Environment-driven settings. No module here imports torch or other heavy
ML libraries, so `import backend.main` stays cheap regardless of DETECTOR.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from backend.contracts import RuleScope
from backend.f1.visual_checks import VisualCheckSettings

try:
    from backend.vlm.config import VlmSettings
except ModuleNotFoundError:
    from pydantic import BaseModel

    class VlmSettings(BaseModel):  # type: ignore[no-redef]
        """Placeholder matching the agreed shape until WP2 adds backend/vlm/config.py.

        Re-check: once backend/vlm/config.py exists, this branch is dead code
        and the real `VlmSettings` (with a required `model` field) is used.
        """

        base_url: str = "http://127.0.0.1:8010/v1"
        model: str = ""
        max_side: int = 768
        max_in_flight: int = 8
        request_timeout_s: float = 60.0
        stop_margin_s: float = 15.0
        max_failed_frac: float = 0.30
        fill_step_s: float = 2.0


ROOT = Path(__file__).resolve().parents[1]
DetectorName = Literal["vlm", "f1"]


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    detector: DetectorName = "f1"
    # "jury": report only jury-eligible rules (the submission). "detector": every enabled rule,
    # citations marked pending (experiments). See knowledge/README.md.
    rule_scope: RuleScope = "jury"
    knowledge_dir: Path = ROOT / "knowledge"
    job_budget_s: float = 270.0
    max_upload_bytes: int = 64 * 1024 * 1024
    results_ttl_hours: float = 24.0
    work_dir: Path = ROOT / "runtime"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    f1_codex_path: Path = ROOT / "config" / "f1_codex.yaml"
    weights_dir: Path = ROOT / "weights"
    perception_config: Path = ROOT / "config" / "perception.yaml"
    overrides_path: Path = ROOT / "config" / "overrides.yaml"
    cache_dir: Path = ROOT / "runtime" / "perception_cache"
    device: str = "auto"
    cpu_threads: int = 4
    reuse_perception: bool = True
    # `VlmSettings.model` may be required (no default) once WP2's real class
    # lands, so this is built explicitly in __post_init__ rather than via a
    # dataclass default_factory.
    vlm: VlmSettings | None = None
    # Initial integration is opt-in until the local model has been measured.
    visual_checks: VisualCheckSettings = field(default_factory=VisualCheckSettings)

    @property
    def traces_dir(self) -> Path:
        """Per-job F1 trace files (`<job_id>.json`), see `backend.f1.detector`."""
        return self.work_dir / "traces"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError(
                "API_KEY must be set and non-empty; define it in .env, never hardcode a real key"
            )
        if self.detector not in ("vlm", "f1"):
            raise ValueError("DETECTOR must be 'vlm' or 'f1'")
        if self.rule_scope not in ("jury", "detector"):
            raise ValueError("RULE_SCOPE must be 'jury' or 'detector'")
        if self.job_budget_s <= 0:
            raise ValueError("job_budget_s must be positive")
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be positive")
        if self.results_ttl_hours <= 0:
            raise ValueError("results_ttl_hours must be positive")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        if self.cpu_threads < 1:
            raise ValueError("cpu_threads must be positive")
        if self.vlm is None:
            object.__setattr__(self, "vlm", VlmSettings(model=os.environ.get("VLM_MODEL", "")))

    @classmethod
    def from_env(cls) -> Settings:
        detector = os.environ.get("DETECTOR", "f1")
        if detector not in ("vlm", "f1"):
            raise ValueError("DETECTOR must be 'vlm' or 'f1'")
        return cls(
            api_key=os.environ.get("API_KEY", ""),
            detector=detector,  # type: ignore[arg-type]
            rule_scope=os.environ.get("RULE_SCOPE", "jury"),  # type: ignore[arg-type]
            knowledge_dir=Path(os.environ.get("KNOWLEDGE_DIR", str(ROOT / "knowledge"))),
            job_budget_s=float(os.environ.get("JOB_BUDGET_S", "270")),
            max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", str(64 * 1024 * 1024))),
            results_ttl_hours=float(os.environ.get("RESULTS_TTL_HOURS", "24")),
            work_dir=Path(os.environ.get("WORK_DIR", str(ROOT / "runtime"))),
            f1_codex_path=Path(
                os.environ.get("F1_CODEX_PATH", str(ROOT / "config" / "f1_codex.yaml"))
            ),
            weights_dir=Path(os.environ.get("WEIGHTS_DIR", str(ROOT / "weights"))),
            perception_config=Path(
                os.environ.get("PERCEPTION_CONFIG", str(ROOT / "config" / "perception.yaml"))
            ),
            overrides_path=Path(
                os.environ.get("OVERRIDES_PATH", str(ROOT / "config" / "overrides.yaml"))
            ),
            cache_dir=Path(os.environ.get("CACHE_DIR", str(ROOT / "runtime" / "perception_cache"))),
            device=os.environ.get("DEVICE", "auto"),
            cpu_threads=int(os.environ.get("CPU_THREADS", "4")),
            vlm=VlmSettings(
                base_url=os.environ.get("VLM_BASE_URL", "http://127.0.0.1:8010/v1"),
                model=os.environ.get("VLM_MODEL", ""),
                max_side=int(os.environ.get("VLM_MAX_SIDE", "768")),
                max_in_flight=int(os.environ.get("VLM_MAX_IN_FLIGHT", "8")),
                request_timeout_s=float(os.environ.get("VLM_REQUEST_TIMEOUT_S", "60")),
                stop_margin_s=float(os.environ.get("VLM_STOP_MARGIN_S", "15")),
                max_failed_frac=float(os.environ.get("VLM_MAX_FAILED_FRAC", "0.30")),
                fill_step_s=float(os.environ.get("VLM_FILL_STEP_S", "2.0")),
            ),
            visual_checks=VisualCheckSettings(
                enabled=os.environ.get("F1_VISUAL_CHECKS", "0"),
                model_path=os.environ.get("F1_VISUAL_MODEL_PATH") or None,
                worker_python=os.environ.get("F1_VISUAL_WORKER_PYTHON") or None,
                cache_dir=os.environ.get("F1_VISUAL_CACHE_DIR") or None,
                families=tuple(os.environ.get("F1_VISUAL_FAMILIES", "safe").split(",")),
                max_checks=int(os.environ.get("F1_VISUAL_MAX_CHECKS", "24")),
                max_video_s=float(os.environ.get("F1_VISUAL_BUDGET_S", "60")),
                request_timeout_s=float(os.environ.get("F1_VISUAL_REQUEST_TIMEOUT_S", "45")),
                stop_margin_s=float(os.environ.get("F1_VISUAL_STOP_MARGIN_S", "5")),
                crop_margin=float(os.environ.get("F1_VISUAL_CROP_MARGIN", "0.25")),
                max_side=int(os.environ.get("F1_VISUAL_MAX_SIDE", "896")),
                cpu_threads=int(os.environ.get("CPU_THREADS", "4")),
            ),
        )
