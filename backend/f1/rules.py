"""One deterministic function per supported codex ID; legal prose lives only in YAML."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.f1.calibration import in_zone
from backend.f1.codex import Codex, Rule
from backend.f1.events import EventLog
from backend.f1.vision_types import (
    Detection,
    Event,
    Observation,
    Scene,
    center,
    contains,
    distance,
)

if TYPE_CHECKING:  # desk_objects needs cv2 at import time
    from backend.f1.desk_objects import DeskObject

LEFT_BEHIND_SEC = 2.0


@dataclass
class Finding:
    rule_id: str
    timestamp_sec: float
    facts: dict = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class Context:
    codex: Codex
    log: EventLog
    observations: list[Observation]
    scene: Scene
    duration: float
    # A18: items found by desk change and named by their history (backend/f1/desk_objects.py);
    # None keeps the detector's labels as the source of items for the leave rules.
    desk_objects: "list[DeskObject] | None" = None

    def rule(self, identity: str) -> Rule:
        return next(rule for rule in self.codex.rules if rule.id == identity)

    def events(self, kind: str) -> list[Event]:
        return [event for event in self.log.events if event.type == kind]

    def nearby(self, timestamp: float) -> Observation:
        return min(self.observations, key=lambda frame: abs(frame.timestamp_sec - timestamp))

    def state_at(self, family: str, timestamp: float) -> str:
        matches = [
            event
            for event in self.log.events
            if event.timestamp_sec <= timestamp
            and (
                event.type == "SCREEN"
                if family == "laptop"
                else event.type.startswith(family.upper() + "_")
            )
            and "state" in event.facts
        ]
        return str(matches[-1].facts["state"]) if matches else "unknown"

    def intervals(self, kind: str):
        starts = {}
        for event in self.log.events:
            key = event.facts.get("condition_id", "")
            if event.type == kind + "_START":
                starts[key] = event
            elif event.type == kind + "_END" and key in starts:
                start = starts.pop(key)
                yield start, event.timestamp_sec - start.timestamp_sec

    def leaves(self):
        candidates = [e for e in self.events("EXIT") if e.facts.get("role") == "cashier"]
        candidates += [
            event for event, duration in self.intervals("WORKSTATION_AWAY") if duration >= 0.6
        ]
        output = []
        for event in sorted(candidates, key=lambda e: e.timestamp_sec):
            if not output or event.timestamp_sec - output[-1].timestamp_sec > 4:
                output.append(event)
        return output

    def on_desk(self, timestamp: float, labels: set[str]) -> list[Detection]:
        frame = self.nearby(min(timestamp + 0.2, self.duration))
        people = [d for d in frame.detections if d.label == "person"]
        # The open-vocabulary "tablet"/"document" prompts also fire on the laptop and the
        # counter themselves; those are workstation fixtures, not items left on the desk.
        fixtures = [
            self.scene.objects[n].box for n in ("laptop", "counter") if n in self.scene.objects
        ]
        return [
            d
            for d in frame.detections
            if d.label in labels
            and in_zone(self.scene, "desk", center(d.box))
            and not any(contains(box, center(d.box), 0.01) for box in fixtures)
            and not any(
                distance(center(d.box), hand) < 0.045 for p in people for hand in p.wrists()
            )
        ]

    def has_event(self, kind: str, start: float, end: float, **facts) -> bool:
        return any(
            start <= event.timestamp_sec <= end
            and all(event.facts.get(k) == v for k, v in facts.items())
            for event in self.events(kind)
        )


def left_with(ctx: Context, rule_id: str, labels: set[str]) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("desk"):
        return []
    result = []
    for leave in ctx.leaves():
        # Left behind = still on the desk a moment after the cashier walked off; a cashier
        # standing up usually picks the item up on the way.
        start, later = leave.timestamp_sec, leave.timestamp_sec + LEFT_BEHIND_SEC
        facts: dict = {"actor_id": leave.facts.get("actor_id", "")}
        if ctx.desk_objects is None:
            kept = {d.track_id for d in ctx.on_desk(later, labels)}
            objects = [d for d in ctx.on_desk(start, labels) if d.track_id in kept]
            facts["track_ids"] = [d.track_id for d in objects]
            confidence = min((d.score for d in objects), default=0)
        else:
            objects = [
                o
                for o in ctx.desk_objects
                if o.kind in labels and o.present(start) and o.present(later)
            ]
            facts["track_ids"] = [o.track_id for o in objects]
            if objects:
                facts["box"] = list(objects[0].box)
                facts["object"] = objects[0].kind
                facts["clues"] = sorted({clue for o in objects for clue in o.clues})
            confidence = 1.0
        if objects:
            result.append(Finding(rule_id, start, facts, confidence))
    return result


def l_no_cash_on_leave(ctx: Context) -> list[Finding]:
    return left_with(ctx, "L-NO-CASH-ON-LEAVE", {"cash", "bundle"})


def l_no_bag_on_leave(ctx: Context) -> list[Finding]:
    return left_with(ctx, "L-NO-BAG-ON-LEAVE", {"bag"})


def l_no_docs_on_leave(ctx: Context) -> list[Finding]:
    return left_with(ctx, "L-NO-DOCS-ON-LEAVE", {"document", "id_card", "tablet"})


def l_pc_locked(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("laptop"):
        return []
    return [
        Finding("L-PC-LOCKED", event.timestamp_sec, {**event.facts, "static_objects": ["laptop"]})
        for event in ctx.leaves()
        if ctx.state_at("laptop", event.timestamp_sec) == "working"
    ]


def sustained(ctx: Context, rule_id: str, kind: str, *, strict: bool = True) -> list[Finding]:
    minimum = ctx.rule(rule_id).min_duration_sec or 0
    return [
        Finding(rule_id, event.timestamp_sec, {**event.facts, "duration_sec": duration})
        for event, duration in ctx.intervals(kind)
        if (duration > minimum if strict else duration >= minimum)
    ]


def s_safe_closed(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("safe"):
        return []
    return sustained(ctx, "S-SAFE-CLOSED", "SAFE_UNATTENDED")


def s_clean_desk_handover(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("desk"):
        return []
    output = []
    for session in ctx.events("SESSION_START"):
        visible = {d.track_id for d in ctx.on_desk(session.timestamp_sec, {"cash", "bundle"})}
        states = {}
        for event in ctx.events("CASH_STATE"):
            if event.timestamp_sec > session.timestamp_sec:
                break
            states[event.facts["cash_id"]] = event
        previous = [
            event
            for event in states.values()
            if event.facts.get("session_id")
            and event.facts["session_id"] != session.facts["session_id"]
            and event.facts.get("location") == "desk"
            and event.facts.get("track_id") in visible
        ]
        if previous:
            output.append(
                Finding(
                    "S-CLEAN-DESK-HANDOVER",
                    session.timestamp_sec,
                    {**session.facts, "track_ids": [str(e.facts["track_id"]) for e in previous]},
                )
            )
    return output


def a_door_lock(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("door"):
        return []
    window = ctx.rule("A-DOOR-LOCK").min_duration_sec
    if window is None:
        raise ValueError("A-DOOR-LOCK needs a numeric codex duration")
    output = []
    for entry in ctx.events("ENTER"):
        end = entry.timestamp_sec + window
        if not entry.facts.get("observed_entry") or end > ctx.duration:
            continue
        closed = ctx.has_event("DOOR_CLOSED", entry.timestamp_sec, end)
        touched = ctx.has_event("HAND_ON_DOOR", entry.timestamp_sec, end)
        state = ctx.state_at("door", end)
        if not closed and not touched and state == "open":
            output.append(
                Finding(
                    "A-DOOR-LOCK",
                    entry.timestamp_sec,
                    {**entry.facts, "static_objects": ["door"], "window_end": end},
                )
            )
    return output


def a_outsider_zone(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles"):
        return []
    return sustained(ctx, "A-OUTSIDER-ZONE", "PERSON_IN_CASHIER_ZONE")


def a_second_person(ctx: Context) -> list[Finding]:
    output = []
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("hands"):
        return output
    for event in ctx.events("HANDOVER"):
        session = ctx.log.sessions.get(str(event.facts.get("session_id")))
        if (
            session
            and event.facts.get("from_id") != session["client_id"]
            and event.facts.get("from_role") in {"client", "collector", "visitor", "outsider"}
            and (event.facts.get("to_role") == "cashier" or event.facts.get("to_id") == "desk")
        ):
            output.append(Finding("A-SECOND-PERSON", event.timestamp_sec, event.facts))
    return output


def c_count_before_exit(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("counter") or not ctx.log.coverage.get("roles"):
        return []
    output = []
    for event in ctx.events("SESSION_END"):
        session = ctx.log.sessions.get(str(event.facts["session_id"]))
        if not session or not event.facts.get("confirmed_exit") or not session["cash_ids"]:
            continue
        counted = set(session["counted_cash_ids"])
        count_observed = ctx.has_event(
            "COUNT_END",
            session["start"],
            event.timestamp_sec,
            session_id=event.facts["session_id"],
        )
        if set(session["cash_ids"]) - counted and not count_observed:
            output.append(Finding("C-COUNT-BEFORE-EXIT", event.timestamp_sec, event.facts))
    return output


def c_id_before_cash(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("hands"):
        return []
    seen = set()
    output = []
    for event in ctx.events("HANDOVER"):
        identity = event.facts.get("session_id", "")
        session = ctx.log.sessions.get(str(identity))
        if not session or identity in seen or event.facts.get("object") not in {"cash", "bundle"}:
            continue
        if event.facts.get("from_id") != session["client_id"]:
            continue
        seen.add(identity)
        if session["observed_entry"] and not ctx.has_event(
            "ID_SHOWN", session["start"], event.timestamp_sec, session_id=identity
        ):
            output.append(Finding("C-ID-BEFORE-CASH", event.timestamp_sec, event.facts))
    return output


def collector_transfers(ctx: Context):
    limit = ctx.rule("K-SEAL-CHECK").min_duration_sec
    if limit is None:
        raise ValueError("K-SEAL-CHECK needs a numeric codex duration")
    for transfer in ctx.events("HANDOVER"):
        if transfer.facts.get("object") != "bag" or transfer.facts.get("from_role") != "collector":
            continue
        exits = [
            event
            for event in ctx.events("EXIT")
            if event.facts.get("actor_id") == transfer.facts.get("from_id")
            and 0 <= event.timestamp_sec - transfer.timestamp_sec <= limit
        ]
        if exits:
            yield transfer, exits[0]


def k_collector_doc(ctx: Context) -> list[Finding]:
    output = []
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("hands"):
        return output
    for transfer, exit_event in collector_transfers(ctx):
        actor = transfer.facts["from_id"]
        enters = [
            event.timestamp_sec
            for event in ctx.events("ENTER")
            if event.facts.get("actor_id") == actor
        ]
        if enters and not ctx.has_event(
            "ID_SHOWN", min(enters), exit_event.timestamp_sec, actor_id=actor
        ):
            output.append(Finding("K-COLLECTOR-DOC", transfer.timestamp_sec, transfer.facts))
    return output


def k_seal_check(ctx: Context) -> list[Finding]:
    output = []
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("hands"):
        return output
    for transfer, exit_event in collector_transfers(ctx):
        if not ctx.has_event(
            "BAG_INSPECTED",
            max(0, transfer.timestamp_sec - 1),
            exit_event.timestamp_sec,
            track_id=transfer.facts.get("track_id"),
        ):
            output.append(Finding("K-SEAL-CHECK", transfer.timestamp_sec, transfer.facts))
    return output


def k_recount_before_safe(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("safe") or not ctx.log.coverage.get("counter"):
        return []
    output = []
    origin = {}
    for event in ctx.events("CASH_STATE"):
        identity = event.facts["cash_id"]
        if event.facts.get("bag_open_seen"):
            origin.setdefault(identity, event.timestamp_sec)
        if (
            event.facts.get("location") == "safe"
            and identity in origin
            and event.facts.get("kind") == "bundle"
        ):
            counted = ctx.has_event("COUNT_END", origin[identity], event.timestamp_sec)
            if not event.facts.get("counted") and not counted:
                output.append(
                    Finding(
                        "K-RECOUNT-BEFORE-SAFE",
                        event.timestamp_sec,
                        {**event.facts, "static_objects": ["safe"]},
                    )
                )
    return output


def w_no_personal_items(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("desk"):
        return []
    return sustained(ctx, "W-NO-PERSONAL-ITEMS", "PERSONAL_ON_DESK")


def w_no_food(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("desk") or not ctx.log.coverage.get("hands"):
        return []
    return sustained(ctx, "W-NO-FOOD", "FOOD_NEAR_HEAD", strict=False)


RULES = {
    "L-NO-CASH-ON-LEAVE": l_no_cash_on_leave,
    "L-NO-BAG-ON-LEAVE": l_no_bag_on_leave,
    "L-NO-DOCS-ON-LEAVE": l_no_docs_on_leave,
    "L-PC-LOCKED": l_pc_locked,
    "S-SAFE-CLOSED": s_safe_closed,
    "S-CLEAN-DESK-HANDOVER": s_clean_desk_handover,
    "A-DOOR-LOCK": a_door_lock,
    "A-OUTSIDER-ZONE": a_outsider_zone,
    "A-SECOND-PERSON": a_second_person,
    "C-COUNT-BEFORE-EXIT": c_count_before_exit,
    "C-ID-BEFORE-CASH": c_id_before_cash,
    "K-COLLECTOR-DOC": k_collector_doc,
    "K-SEAL-CHECK": k_seal_check,
    "K-RECOUNT-BEFORE-SAFE": k_recount_before_safe,
    "W-NO-PERSONAL-ITEMS": w_no_personal_items,
    "W-NO-FOOD": w_no_food,
}


def evaluate_rules(ctx: Context) -> list[Finding]:
    identities = {rule.id for rule in ctx.codex.rules}
    if missing := set(RULES) - identities:
        raise ValueError(f"Required rules absent from codex: {sorted(missing)}")
    output = []
    for identity, function in RULES.items():
        rule = ctx.rule(identity)
        if not rule.title or not rule.description_template:
            raise ValueError(f"Missing codex report template: {identity}; regenerate codex.yaml")
        for finding in function(ctx):
            if finding.rule_id != identity or not 0 <= finding.timestamp_sec <= ctx.duration:
                raise ValueError("Invalid rule finding")
            if not any(
                previous.rule_id == finding.rule_id
                and abs(previous.timestamp_sec - finding.timestamp_sec) < 1
                for previous in output
            ):
                output.append(finding)
    return sorted(output, key=lambda finding: (finding.timestamp_sec, finding.rule_id))
