"""Hand-written event timelines per clip, and their comparison with a run's traces.

The team writes what really happens in each open clip (who does what, when). Comparing that
with the checker's per-job trace scores each layer (roles, enter/exit, door/safe, counting,
handovers) instead of only the final verdict. Annotations live next to the gateway state and
never reach the checker.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Actor = Literal["cashier", "client", "collector", "other", "unknown"]
Action = Literal[
    "enter",
    "exit",
    "sit",
    "stand_up",
    "leave_desk",
    "return_desk",
    "hand_over",
    "take",
    "place_item",
    "count_machine",
    "count_manual",
    "open_safe",
    "close_safe",
    "open_door",
    "close_door",
    "show_id",
    "lock_screen",
    "other",
]
Item = Literal[
    "none",
    "cash",
    "bundle",
    "bag",
    "seal",
    "key",
    "id_card",
    "document",
    "tablet",
    "phone",
    "cup_food",
    "handbag_coat",
    "other",
]
Place = Literal["none", "desk", "safe", "counter", "hand", "bag", "door", "outside", "other"]
Layout = Literal["unset", "over_shoulder", "facing_cashier", "side", "other"]

# Trace event type -> the truth action it reports. Truth actions without a system event
# (sit, take, count_manual, ...) are scored as "not detectable".
EVENT_ACTION = {
    "EXIT": "exit",
    "WORKSTATION_AWAY_START": "leave_desk",
    "WORKSTATION_AWAY_END": "return_desk",
    "HANDOVER": "hand_over",
    "COUNT_START": "count_machine",
    "SAFE_OPEN": "open_safe",
    "SAFE_CLOSED": "close_safe",
    "DOOR_OPEN": "open_door",
    "DOOR_CLOSED": "close_door",
    "ID_SHOWN": "show_id",
}
DETECTABLE = {*EVENT_ACTION.values(), "enter", "lock_screen"}
INITIAL_STATE_SEC = 2.0


def reported_action(event: dict) -> str | None:
    kind, facts = event["type"], event.get("facts", {})
    if kind == "ENTER":  # also emitted for people already in the room at the first frame
        return "enter" if facts.get("observed_entry") else None
    if kind == "SCREEN":
        return "lock_screen" if facts.get("state") in {"locked", "closed"} else None
    return EVENT_ACTION.get(kind)


def reported_actions(events: list[dict]) -> list[str | None]:
    """`reported_action` per event, except the first door/safe state of a clip: within the
    first seconds that is the state the clip starts in, not someone opening or closing it."""
    seen: set[str] = set()
    actions = []
    for event in events:
        action = reported_action(event)
        family = event["type"].split("_")[0]
        if family in {"SAFE", "DOOR"} and family not in seen:
            seen.add(family)
            if event["timestamp_sec"] <= INITIAL_STATE_SEC:
                action = None
        actions.append(action)
    return actions


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t_start: float = Field(ge=0, le=10_000)
    t_end: float | None = Field(default=None, ge=0, le=10_000)
    actor: Actor
    actor_desc: str = Field(default="", max_length=80)
    action: Action
    item: Item = "none"
    place: Place = "none"
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def end_after_start(self) -> Row:
        if self.t_end is not None and self.t_end < self.t_start:
            raise ValueError("t_end must not be before t_start")
        return self


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layout: Layout = "unset"
    people_max: int = Field(default=0, ge=0, le=20)
    summary: str = Field(default="", max_length=2000)
    annotator: str = Field(default="", max_length=60)
    status: Literal["draft", "done"] = "draft"
    rows: list[Row] = Field(default_factory=list, max_length=500)


class Stored(Annotation):
    clip: str
    version: float = 0.0  # unix time of the last save; 0 = never saved


class VersionConflict(Exception):
    """Someone else saved this clip after the caller loaded it."""


def vocabulary() -> dict[str, list[str]]:
    return {
        name: list(kind.__args__)
        for name, kind in {
            "actor": Actor,
            "action": Action,
            "item": Item,
            "place": Place,
            "layout": Layout,
        }.items()
    } | {"detectable": sorted(DETECTABLE)}


class AnnotationStore:
    """One JSON file per clip key (`X-34.json`); keys come from `clip_key`, never raw names."""

    def __init__(self, directory: Path):
        self.directory = directory

    def path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def load(self, key: str) -> Stored:
        path = self.path(key)
        if not path.is_file():
            return Stored(clip=key)
        return Stored.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, key: str, annotation: Annotation, base_version: float) -> Stored:
        current = self.load(key)
        if current.version != base_version:
            raise VersionConflict(f"{key} was saved by {current.annotator or 'someone'} meanwhile")
        stored = Stored(clip=key, version=time.time(), **annotation.model_dump())
        self.directory.mkdir(parents=True, exist_ok=True)
        partial = self.path(key).with_suffix(".partial")
        partial.write_text(stored.model_dump_json(indent=1), encoding="utf-8")
        partial.replace(self.path(key))
        return stored

    def all(self) -> list[Stored]:
        if not self.directory.is_dir():
            return []
        return [self.load(p.stem) for p in sorted(self.directory.glob("*.json"))]


def score_clip(annotation: Stored, events: list[dict], tolerance: float = 2.0) -> dict:
    """Greedy one-to-one matching in time order: each truth row takes the nearest unused
    trace event of a matching type within `tolerance` seconds of its start."""
    events = sorted(events, key=lambda e: e["timestamp_sec"])
    actions = reported_actions(events)
    used: set[int] = set()
    rows = []
    for row in sorted(annotation.rows, key=lambda r: r.t_start):
        candidates = [
            (abs(e["timestamp_sec"] - row.t_start), i)
            for i, e in enumerate(events)
            if i not in used
            and actions[i] == row.action
            and abs(e["timestamp_sec"] - row.t_start) <= tolerance
        ]
        hit = min(candidates)[1] if candidates else None
        if hit is not None:
            used.add(hit)
        event = events[hit] if hit is not None else None
        role = event.get("facts", {}).get("role") if event else None
        rows.append(
            {
                **row.model_dump(),
                "detectable": row.action in DETECTABLE,
                "matched_t": event["timestamp_sec"] if event else None,
                "matched_role": role,
                "role_ok": (role == row.actor) if role and row.actor != "unknown" else None,
            }
        )
    extra = [
        {
            "t": e["timestamp_sec"],
            "action": actions[i],
            "type": e["type"],
            "role": e.get("facts", {}).get("role"),
        }
        for i, e in enumerate(events)
        if actions[i] and i not in used
    ]
    return {"clip": annotation.clip, "rows": rows, "unmatched_events": extra}


def summarize(clips: list[dict]) -> dict:
    """Per action: recall over truth rows, precision over the trace events of that type."""
    per_action: dict[str, dict[str, int]] = {}
    roles = {"ok": 0, "checked": 0}
    for clip in clips:
        for row in clip["rows"]:
            stats = per_action.setdefault(row["action"], {"truth": 0, "found": 0, "extra": 0})
            stats["truth"] += 1
            stats["found"] += row["matched_t"] is not None
            if row["role_ok"] is not None:
                roles["checked"] += 1
                roles["ok"] += row["role_ok"]
        for event in clip["unmatched_events"]:
            stats = per_action.setdefault(event["action"], {"truth": 0, "found": 0, "extra": 0})
            stats["extra"] += 1
    for action, stats in per_action.items():
        stats["detectable"] = action in DETECTABLE
    return {"clips": len(clips), "per_action": per_action, "roles": roles}


def trace_events(raw: bytes) -> list[dict]:
    return json.loads(raw)["events"]
