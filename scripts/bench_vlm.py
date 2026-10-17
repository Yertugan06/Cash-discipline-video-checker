"""Benchmarks VlmDetector against a *live* vLLM server (WP2 gate G1, implementation-plan.md).

Prints only aggregates: wall time, frames done/planned, coverage mode, s/frame
and peak VRAM (via `nvidia-smi`, if present). Never prints per-frame states
(SHARED_BRIEF.md privacy rule: no `states/`/`violations/` content, ever).

This cannot be run on this machine (no GPU, no vLLM). Run it on the GPU VM
once vLLM is serving on 127.0.0.1:8010 (see deploy/vllm/serve.sh):

    .venv/bin/python scripts/bench_vlm.py path/to/clip.mov --model Qwen/Qwen3.5-9B
    .venv/bin/python scripts/bench_vlm.py path/to/clip.mov --model Qwen/Qwen3.5-9B --deadline-s 60
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> None:
    args = _parse_args()

    try:
        from backend.media import probe
        from backend.plan import build_plan
    except ImportError as exc:  # WP1's modules; not yet available during early development
        sys.exit(f"backend.media / backend.plan are not available yet (WP1 owns them): {exc}")

    from backend.vlm.config import VlmSettings
    from backend.vlm.detector import VlmDetector

    settings = VlmSettings(
        base_url=args.base_url,
        model=args.model,
        max_side=args.max_side,
        max_in_flight=args.max_in_flight,
    )

    info = probe(args.video)
    deadline = time.monotonic() + args.deadline_s
    plan = build_plan(info, deadline)

    vram = _PeakVram()
    vram.start()
    t0 = time.monotonic()
    with VlmDetector(settings, rules=[]) as detector:
        result = detector.detect(args.video, info, plan)
    wall_s = time.monotonic() - t0
    vram.stop()

    cov = result.coverage
    s_per_frame = wall_s / cov.done if cov.done else float("nan")
    print(f"video: {args.video}")
    print(f"duration_s: {info.duration_sec:.1f}")
    print(f"wall_s: {wall_s:.1f}")
    print(f"frames: done={cov.done} planned={cov.planned} failed={cov.failed}")
    print(f"coverage_mode: {cov.mode} deadline_hit: {cov.deadline_hit} step_s: {cov.step_s}")
    print(f"s_per_frame: {s_per_frame:.2f}")
    if vram.peak_mib is not None:
        print(f"peak_vram_mib: {vram.peak_mib}")
    else:
        print("peak_vram_mib: n/a (nvidia-smi not found)")
    if result.warnings:
        print("warnings:")
        for w in result.warnings:
            print(f"  - {w}")


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("video", type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8010/v1")
    ap.add_argument(
        "--deadline-s",
        type=float,
        default=240.0,
        help="seconds from now for the sampling plan's deadline (per-job budget is 270 s; "
        "architecture.md §4)",
    )
    ap.add_argument("--max-side", type=int, default=768)
    ap.add_argument("--max-in-flight", type=int, default=8)
    return ap.parse_args()


class _PeakVram:
    """Polls `nvidia-smi` on a background thread and tracks the peak `memory.used`."""

    def __init__(self, interval_s: float = 1.0) -> None:
        self._interval_s = interval_s
        self._available = shutil.which("nvidia-smi") is not None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_mib: int | None = None

    def start(self) -> None:
        if not self._available:
            return
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=self._interval_s * 2)
        self._sample()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            self._sample()

    def _sample(self) -> None:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return
        values = [int(line.strip()) for line in out.stdout.splitlines() if line.strip()]
        if not values:
            return
        sample = max(values)
        if self.peak_mib is None or sample > self.peak_mib:
            self.peak_mib = sample


if __name__ == "__main__":
    main()
