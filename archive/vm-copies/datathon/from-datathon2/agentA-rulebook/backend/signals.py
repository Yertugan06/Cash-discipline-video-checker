"""Time-series signals over tracked observations, shared by rules and probes.

All signals are relative to the clip's own scene baseline (first seconds), so a
static layout feature that is present from the start never counts as a change.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.calibration import in_zone
from backend.vision_types import Detection, Observation, Scene, overlap

BASELINE_SEC = 2.0


def people(observation: Observation, min_score: float = 0.4) -> list[Detection]:
    """Person detections with duplicate boxes removed (tracker splits, NMS leftovers)."""
    kept: list[Detection] = []
    candidates = [d for d in observation.detections if d.label == "person" and d.score >= min_score]
    for person in sorted(candidates, key=lambda d: d.score, reverse=True):
        if all(overlap(person.box, other.box) < 0.3 for other in kept):
            kept.append(person)
    return kept


def zone_counts(scene: Scene, observations: list[Observation], zone: str) -> list[tuple[float, int]]:
    return [
        (o.timestamp_sec, sum(in_zone(scene, zone, p.position()) for p in people(o)))
        for o in observations
    ]


def baseline_count(series: list[tuple[float, int]]) -> int:
    early = [count for t, count in series if t <= BASELINE_SEC]
    return int(np.median(early)) if early else 0


def runs(series: list[tuple[float, bool]], max_gap: float = 0.6) -> list[tuple[float, float]]:
    """Intervals where the flag holds, bridging false gaps up to max_gap seconds."""
    output: list[list[float]] = []
    for t, flag in series:
        if not flag:
            continue
        if output and t - output[-1][1] <= max_gap + 1e-6:
            output[-1][1] = t
        else:
            output.append([t, t])
    return [(a, b) for a, b in output]


def excess_runs(scene: Scene, observations: list[Observation], zone: str, minimum: int = 2):
    """Intervals with more people in `zone` than at the start (and at least `minimum`)."""
    series = zone_counts(scene, observations, zone)
    need = max(minimum, baseline_count(series) + 1)
    return runs([(t, c >= need) for t, c in series])


@lru_cache(maxsize=64)
def load_extras(path: str) -> dict[str, np.ndarray]:
    if not path or not Path(path).is_file():
        return {}
    with np.load(path) as data:
        return {key: data[key].astype(np.float32) for key in data.files}


def mean_embedding(extras: dict, name: str, start: float, end: float) -> np.ndarray | None:
    if name not in extras or "time" not in extras:
        return None
    times = extras["time"]
    rows = extras[name][(times >= start) & (times <= end)]
    rows = rows[np.isfinite(rows).all(axis=1)]
    if not len(rows):
        return None
    vector = rows.mean(axis=0)
    return vector / max(np.linalg.norm(vector), 1e-8)


def similarity(extras: dict, name: str, a: tuple[float, float], b: tuple[float, float]):
    first, second = mean_embedding(extras, name, *a), mean_embedding(extras, name, *b)
    if first is None or second is None:
        return None
    return float(first @ second)
