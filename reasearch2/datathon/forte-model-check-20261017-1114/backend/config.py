import math
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    work_dir: Path = ROOT / "runtime"
    codex_path: Path = ROOT / "codex.yaml"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    sample_fps: float = 5.0
    max_upload_bytes: int = 64 * 1024 * 1024
    max_duration_sec: float = 180.0
    timeout_sec: float = 300.0
    weights_dir: Path = ROOT / "weights"
    perception_config: Path = ROOT / "config/perception.yaml"
    overrides_path: Path = ROOT / "config/overrides.yaml"
    cache_dir: Path = ROOT / "runtime/perception_cache"
    device: str = "auto"
    cpu_threads: int = 4
    reuse_perception: bool = True

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("API_KEY must be set and non-empty")
        for name in ("sample_fps", "max_duration_sec", "timeout_sec"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if self.sample_fps > 30:
            raise ValueError("sample_fps must be at most 30")
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be positive")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        if self.cpu_threads < 1:
            raise ValueError("cpu_threads must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.environ.get("API_KEY", ""),
            work_dir=Path(os.environ.get("WORK_DIR", ROOT / "runtime")),
            codex_path=Path(os.environ.get("CODEX_PATH", ROOT / "codex.yaml")),
            sample_fps=float(os.environ.get("SAMPLE_FPS", "5")),
            weights_dir=Path(os.environ.get("WEIGHTS_DIR", ROOT / "weights")),
            perception_config=Path(
                os.environ.get("PERCEPTION_CONFIG", ROOT / "config/perception.yaml")
            ),
            overrides_path=Path(os.environ.get("OVERRIDES_PATH", ROOT / "config/overrides.yaml")),
            cache_dir=Path(os.environ.get("CACHE_DIR", ROOT / "runtime/perception_cache")),
            device=os.environ.get("DEVICE", "auto"),
            cpu_threads=int(os.environ.get("CPU_THREADS", "4")),
            timeout_sec=float(os.environ.get("PROCESSING_TIMEOUT_SEC", "300")),
        )
