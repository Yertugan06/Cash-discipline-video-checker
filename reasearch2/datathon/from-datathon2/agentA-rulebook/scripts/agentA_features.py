"""Candidate per-clip features used to set rule thresholds (probe only)."""

from dataclasses import dataclass
from typing import Callable

from backend import signals


@dataclass
class Feature:
    name: str
    family: str
    fn: Callable


def longest(intervals):
    return max((b - a for a, b in intervals), default=0.0)


def outsider(ctx):
    if "cashier" not in ctx.scene.zones:
        return None
    return longest(signals.excess_runs(ctx.scene, ctx.observations, "cashier"))


def second(ctx):
    if "client" not in ctx.scene.zones:
        return None
    return longest(signals.excess_runs(ctx.scene, ctx.observations, "client"))


def baseline_cashier(ctx):
    if "cashier" not in ctx.scene.zones:
        return None
    return signals.baseline_count(signals.zone_counts(ctx.scene, ctx.observations, "cashier"))


def leave_times(ctx):
    return [e.timestamp_sec for e in ctx.leaves()]


def pc_contrast(ctx):
    extras = signals.load_extras(ctx.extras_path or "")
    values = []
    for t in leave_times(ctx):
        value = signals.similarity(
            extras, "laptop", (0, max(1.0, t - 3)), (t + 1.5, min(ctx.duration, t + 5))
        )
        if value is not None:
            values.append(value)
    return max(values) if values else None


def desk_change(ctx):
    extras = signals.load_extras(ctx.extras_path or "")
    values = []
    for t in leave_times(ctx):
        for name in [k for k in extras if k.startswith("desk_tile")]:
            value = signals.similarity(
                extras, name, (0, signals.BASELINE_SEC), (t + 1.5, min(ctx.duration, t + 5))
            )
            if value is not None:
                values.append(1 - value)
    return max(values) if values else None


def n_leaves(ctx):
    return float(len(leave_times(ctx)))


def safe_open_max(ctx):
    return max((d for _, d in ctx.intervals("SAFE_UNATTENDED")), default=0.0)


FEATURES = [
    Feature("outsider_excess_sec", "outsider", outsider),
    Feature("cashier_baseline_count", "outsider", baseline_cashier),
    Feature("client_excess_sec", "second", second),
    Feature("n_leaves", "leave", n_leaves),
    Feature("pc_sim_after_vs_start", "pc", pc_contrast),
    Feature("desk_tile_change_max", "leave", desk_change),
    Feature("safe_unattended_max", "safe", safe_open_max),
]
