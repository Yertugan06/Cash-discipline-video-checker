"""Adapter: one of the kit's saved per-video state files -> a typed ``StateTimeline``.

The kit (``archive/vm-copies/datathon/forte_brev_kit/brev_kit``, gitignored, private) writes one
JSON Lines file per video under ``runs/<run>/states/<video>.jsonl``, one row per sampled frame:
``{"video": str, "t": float, "state": dict | None, "ok": bool, "errors": list, "latency_s": float,
"raw": str}``. This module never prints a row's values, only uses the `t`/`ok`/`state` keys needed
to build the typed timeline (privacy rule in AGENTS.md / the shared brief).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.contracts import Coverage, FrameObservation, FrameState, StateTimeline, VideoInfo

_STATE_FIELDS = set(FrameState.model_fields.keys())


def load_kit_states(path: Path) -> StateTimeline:
    """Read one ``<video>.jsonl`` state file and build a ``StateTimeline``.

    Rows where ``ok`` is false, or ``state`` is missing/not a mapping, become
    ``FrameObservation(ok=False, state=None)`` -- unknown, never negative evidence, exactly like
    the kit's own loader (``if r.get('ok') and isinstance(r.get('state'), dict)``).
    """
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    rows.sort(key=lambda r: r["t"])

    frames: list[FrameObservation] = []
    for row in rows:
        ok = bool(row.get("ok")) and isinstance(row.get("state"), dict)
        state = None
        if ok:
            fields = {k: v for k, v in row["state"].items() if k in _STATE_FIELDS}
            state = FrameState(**fields)
        frames.append(
            FrameObservation(
                t=float(row["t"]),
                ok=ok,
                state=state,
                error=None if ok else "kit state: not ok or schema-invalid",
                latency_s=float(row.get("latency_s") or 0.0),
            )
        )

    times = [f.t for f in frames]
    duration = max(times) if times else 0.0
    # Real video bytes are private and not read here; the hash is a stable per-file placeholder.
    sha256 = hashlib.sha256(path.stem.encode("utf-8")).hexdigest()
    info = VideoInfo(sha256=sha256, duration_sec=max(duration, 0.01), width=1, height=1, fps=1.0)
    done = sum(1 for f in frames if f.ok)
    coverage = Coverage(
        step_s=1.0,
        planned=len(frames),
        done=done,
        failed=len(frames) - done,
        deadline_hit=False,
        mode="full",
    )
    return StateTimeline(video=info, frames=frames, coverage=coverage)
