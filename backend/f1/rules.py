"""One deterministic function per supported codex ID; legal prose lives only in YAML."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from math import isfinite
from typing import TYPE_CHECKING

from backend.f1.calibration import in_zone
from backend.f1.codex import Codex, Rule
from backend.f1.events import EventLog, safe_attended, session_client_ids
from backend.f1.vision_types import (
    Detection,
    Event,
    Observation,
    Scene,
    center,
    contains,
    distance,
    overlap,
)

if TYPE_CHECKING:  # desk_objects needs cv2 at import time
    from backend.f1.desk_objects import DeskObject

LEFT_BEHIND_SEC = 2.0
STATE_SAMPLE_GAP_SEC = 0.6


@dataclass
class Finding:
    rule_id: str
    timestamp_sec: float
    facts: dict = field(default_factory=dict)
    confidence: float | None = None


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
    # Still-frame verifier records. Unknown/failure is not evidence of absence, and
    # even successful negative stills cannot establish a whole interval's absence.
    visual_checks: list[dict] | None = None

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

    def verified_checks(
        self, family: str, trigger: Event, timestamp: float | None = None
    ) -> list[dict]:
        states = {
            "door": {"open", "closed", "unknown"},
            "laptop": {"working", "locked", "closed", "unknown"},
            "safe": {"open", "closed", "unknown"},
        }
        output = []
        for check in self.visual_checks or []:
            if not isinstance(check, dict):
                continue
            t, trigger_t, box = check.get("t"), check.get("trigger_t"), check.get("box")
            trigger_name = (
                check.get("parent_trigger")
                if check.get("trigger") == "safe_open_window"
                else check.get("trigger")
            )
            trigger_type = {
                "observed_entry": "ENTER",
                "safe_unattended": "SAFE_UNATTENDED_START",
            }.get(trigger_name, str(trigger_name).upper())
            if (
                check.get("family") != family
                or check.get("diagnostic_only") is True
                or check.get("ok") is not True
                or not isinstance(check.get("answer"), str)
                or check.get("answer") not in states[family]
                or not all(
                    isinstance(check.get(k), str) and check[k].strip()
                    for k in ("source", "question_id", "trigger", "actor_id")
                )
                or trigger_type != trigger.type
                or check["actor_id"] != trigger.facts.get("actor_id")
                or (trigger.type == "ENTER" and check.get("observed_entry") is not True)
                or type(t) not in {int, float}
                or not isfinite(t)
                or not 0 <= t <= self.duration
                or type(trigger_t) not in {int, float}
                or not isfinite(trigger_t)
                or abs(trigger_t - trigger.timestamp_sec) > 1e-6
                or (timestamp is not None and abs(t - timestamp) > STATE_SAMPLE_GAP_SEC)
                or not isinstance(box, (list, tuple))
                or len(box) != 4
                or not all(type(v) in {int, float} and isfinite(v) and 0 <= v <= 1 for v in box)
                or not (box[0] < box[2] and box[1] < box[3])
            ):
                continue
            output.append(check)
        return sorted(
            output,
            key=lambda check: abs(check["t"] - timestamp) if timestamp is not None else check["t"],
        )

    def intervals(self, kind: str):
        starts = {}
        for event in self.log.events:
            key = event.facts.get("condition_id", "")
            if event.type == kind + "_START":
                starts[key] = event
            elif event.type == kind + "_END" and key in starts:
                start = starts.pop(key)
                yield start, event.timestamp_sec - start.timestamp_sec

    def leaves(self, minimum_away: float = 0.6) -> list[Event]:
        candidates = [e for e in self.events("EXIT") if e.facts.get("role") == "cashier"]
        candidates += [
            event
            for event, duration in self.intervals("WORKSTATION_AWAY")
            if duration >= minimum_away
        ]
        output = []
        for event in sorted(candidates, key=lambda e: e.timestamp_sec):
            if not output or event.timestamp_sec - output[-1].timestamp_sec > 4:
                output.append(event)
        return output

    def room_exits(self) -> list[Event]:
        return [
            event
            for event in self.events("EXIT")
            if event.facts.get("role") == "cashier"
            and event.facts.get("confirmed_exit", True) is True
        ]

    def on_desk(self, timestamp: float, labels: set[str]) -> list[Detection]:
        if not self.observations:
            return []
        frame = self.nearby(min(timestamp + 0.2, self.duration))
        if abs(frame.timestamp_sec - timestamp) > 0.6:
            return []
        return self.items_on_desk(frame, labels)

    def items_on_desk(self, frame: Observation, labels: set[str]) -> list[Detection]:
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
            and not any(
                contains(box, center(d.box), self.scene.scaled_distance(0.01)) for box in fixtures
            )
            and not any(
                distance(center(d.box), hand) < self.scene.scaled_distance(0.045)
                for p in people
                for hand in p.wrists()
            )
        ]

    def persistent_on_desk(
        self, start: float, end: float, labels: set[str]
    ) -> dict[str, Detection]:
        tracks: dict[str, dict[float, Detection]] = {}
        for frame in self.observations:
            if start <= frame.timestamp_sec <= end:
                for item in self.items_on_desk(frame, labels):
                    tracks.setdefault(item.track_id, {})[frame.timestamp_sec] = item
        # Corroborate each track in distinct observations; never reuse a nearest frame.
        return {
            track_id: min(samples.values(), key=lambda d: d.score)
            for track_id, samples in tracks.items()
            if len(samples) >= 2
        }

    def has_event(self, kind: str, start: float, end: float, **facts) -> bool:
        return any(
            start <= event.timestamp_sec <= end
            and all(event.facts.get(k) == v for k, v in facts.items())
            for event in self.events(kind)
        )


def left_with(
    ctx: Context, rule_id: str, labels: set[str], *, room_exit: bool = False
) -> list[Finding]:
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("desk"):
        return []
    result = []
    # Documents and laptop checks require leaving the room. Cash/bag checks use
    # workstation departure; walking to equipment must not widen the other rules.
    leaves = ctx.room_exits() if room_exit else ctx.leaves(minimum_away=LEFT_BEHIND_SEC)
    for leave in leaves:
        # Left behind = still on the desk a moment after the cashier walked off; a cashier
        # standing up usually picks the item up on the way. A shorter absence cannot
        # confirm this: the later sample would show the item after the cashier returned.
        start, later = leave.timestamp_sec, leave.timestamp_sec + LEFT_BEHIND_SEC
        if later > ctx.duration:
            continue
        facts: dict = {"actor_id": leave.facts.get("actor_id", "")}
        if ctx.desk_objects is None:
            visible = ctx.persistent_on_desk(
                start - LEFT_BEHIND_SEC / 2, start + LEFT_BEHIND_SEC / 2, labels
            )
            kept = ctx.persistent_on_desk(later, later + LEFT_BEHIND_SEC, labels)
            objects = [d for track_id, d in visible.items() if track_id in kept]
            facts["track_ids"] = [d.track_id for d in objects]
            confidence = min((min(d.score, kept[d.track_id].score) for d in objects), default=0)
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
            away_end = next(
                (
                    event.timestamp_sec + duration
                    for event, duration in ctx.intervals("WORKSTATION_AWAY")
                    if event is leave
                ),
                start,
            )
            # An exit during this absence corroborates leaving, unlike a walk to the safe.
            facts["confirmed_exit"] = leave.type == "EXIT" or ctx.has_event(
                "EXIT", start, away_end, actor_id=facts["actor_id"], role="cashier"
            )
            result.append(Finding(rule_id, start, facts, confidence))
    return result


def l_no_cash_on_leave(ctx: Context) -> list[Finding]:
    # The Knowledge Pack's mechanism for this id: "cash or a cash bag is visible on the desk".
    return left_with(ctx, "L-NO-CASH-ON-LEAVE", {"cash", "bundle", "bag"})


def l_no_bag_on_leave(ctx: Context) -> list[Finding]:
    return left_with(ctx, "L-NO-BAG-ON-LEAVE", {"bag"})


def l_no_docs_on_leave(ctx: Context) -> list[Finding]:
    return left_with(ctx, "L-NO-DOCS-ON-LEAVE", {"document", "id_card", "tablet"}, room_exit=True)


def l_pc_locked(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles"):
        return []
    output = []
    for event in ctx.room_exits():
        checks = ctx.verified_checks("laptop", event, event.timestamp_sec)
        facts = {**event.facts, "static_objects": ["laptop"]}
        if checks:
            state = checks[0]["answer"]
            facts.update(
                state_source=checks[0]["source"],
                state_t=checks[0]["t"],
                question_id=checks[0]["question_id"],
                box=checks[0]["box"],
            )
        elif ctx.observations:
            frame = ctx.nearby(event.timestamp_sec)
            state = frame.states.get("laptop")
            state = (
                state.value
                if state and abs(frame.timestamp_sec - event.timestamp_sec) <= STATE_SAMPLE_GAP_SEC
                else "unknown"
            )
        else:
            state = "unknown"
        if state == "working":
            output.append(Finding("L-PC-LOCKED", event.timestamp_sec, facts))
    return output


def sustained(ctx: Context, rule_id: str, kind: str, *, strict: bool = True) -> list[Finding]:
    minimum = ctx.rule(rule_id).min_duration_sec or 0
    return [
        Finding(rule_id, event.timestamp_sec, {**event.facts, "duration_sec": duration})
        for event, duration in ctx.intervals(kind)
        if (duration > minimum if strict else duration >= minimum)
    ]


def s_safe_closed(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles"):
        return []
    triggers = [
        event
        for event in ctx.log.events
        if event.type in {"HAND_ON_SAFE", "SAFE_UNATTENDED_START", "WORKSTATION_AWAY_START", "EXIT"}
    ]
    # Planner-only departures must be backed by the same visible actor's near-to-away transition.
    was_near = {}
    for frame in sorted(ctx.observations, key=lambda frame: frame.timestamp_sec):
        for person in frame.detections:
            if person.label != "person" or person.role != "cashier":
                continue
            near = safe_attended(ctx.scene, person)
            if was_near.get(person.track_id) and not near:
                triggers.append(
                    Event(
                        type="SAFE_DEPARTURE",
                        timestamp_sec=frame.timestamp_sec,
                        facts={"actor_id": person.track_id},
                    )
                )
            was_near[person.track_id] = near
    checks = [check for trigger in triggers for check in ctx.verified_checks("safe", trigger)]
    if not checks:
        return (
            sustained(ctx, "S-SAFE-CLOSED", "SAFE_UNATTENDED")
            if ctx.log.coverage.get("safe")
            else []
        )
    if "safe" not in ctx.scene.objects:
        return []
    sampled_times = {frame.timestamp_sec for frame in ctx.observations}
    checked = {check["t"]: check for check in checks if check["t"] in sampled_times}
    output, run = [], []
    exits = ctx.room_exits()
    last_cashier_seen = -1.0
    minimum = ctx.rule("S-SAFE-CLOSED").min_duration_sec or 0
    for frame in sorted(ctx.observations, key=lambda frame: frame.timestamp_sec):
        check = checked.get(frame.timestamp_sec)
        raw = frame.states.get("safe")
        state = check["answer"] if check else raw.value if raw else "unknown"
        cashier = next((p for p in frame.detections if p.role == "cashier"), None)
        if cashier is not None:
            last_cashier_seen = frame.timestamp_sec
        exited = any(last_cashier_seen < e.timestamp_sec <= frame.timestamp_sec for e in exits)
        active = state == "open" and (
            (cashier is not None and not safe_attended(ctx.scene, cashier)) or exited
        )
        if not active or (run and frame.timestamp_sec - run[-1] > STATE_SAMPLE_GAP_SEC):
            run = []
        if active and (not run or frame.timestamp_sec > run[-1]):
            run.append(frame.timestamp_sec)
            if frame.timestamp_sec - run[0] > minimum:
                if not output or output[-1].timestamp_sec != run[0]:
                    output.append(Finding("S-SAFE-CLOSED", run[0], {"static_objects": ["safe"]}))
                output[-1].facts.update(
                    duration_sec=frame.timestamp_sec - run[0], window_end=frame.timestamp_sec
                )
    return output


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
            and event.facts.get("track_id")
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


def s_no_merge(ctx: Context) -> list[Finding]:
    """Flag a new cash handover while cash from a different client session remains on the desk."""
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("desk"):
        return []
    output = []
    cash_states: dict[str, Event] = {}
    for event in ctx.log.events:
        if event.type == "CASH_STATE":
            cash_id = str(event.facts.get("cash_id", ""))
            if cash_id:
                cash_states[cash_id] = event
            continue
        if event.type != "HANDOVER" or event.facts.get("object") not in {"cash", "bundle"}:
            continue
        session_id = str(event.facts.get("session_id", ""))
        session = ctx.log.sessions.get(session_id)
        if (
            not session
            or event.facts.get("from_role") != "client"
            or event.facts.get("from_id") not in session_client_ids(session)
            or not (
                event.facts.get("to_role") == "cashier"
                or event.facts.get("to_id") in {"desk", "counter"}
            )
        ):
            continue
        candidates = [
            state
            for state in cash_states.values()
            if state.facts.get("session_id")
            and state.facts.get("session_id") != session_id
            and state.facts.get("location") == "desk"
            and state.facts.get("track_id")
            and state.facts.get("cash_id") != event.facts.get("cash_id")
            and state.facts.get("track_id") != event.facts.get("track_id")
        ]
        if not candidates:
            continue
        visible_tracks = {
            detection.track_id for detection in ctx.on_desk(event.timestamp_sec, {"cash", "bundle"})
        }
        previous = [state for state in candidates if state.facts.get("track_id") in visible_tracks]
        if previous:
            output.append(
                Finding(
                    "S-NO-MERGE",
                    event.timestamp_sec,
                    {
                        "session_id": session_id,
                        "actor_id": event.facts.get("from_id", ""),
                        "track_ids": [str(state.facts["track_id"]) for state in previous],
                        "mechanism": "handover_with_previous_session_cash_visible",
                        "physical_stacking": "unknown",
                    },
                )
            )
    return output


def a_door_lock(ctx: Context) -> list[Finding]:
    if not ctx.observations:
        return []
    window = ctx.rule("A-DOOR-LOCK").min_duration_sec
    if window is None:
        raise ValueError("A-DOOR-LOCK needs a numeric codex duration")
    output = []
    for entry in ctx.events("ENTER"):
        end = entry.timestamp_sec + window
        # A person already in the doorway at the first observation has no observed entry.
        if (
            not entry.facts.get("observed_entry")
            or entry.timestamp_sec <= ctx.observations[0].timestamp_sec
            or end > ctx.duration
        ):
            continue
        checks = ctx.verified_checks("door", entry, end)
        state = (
            checks[0]["answer"]
            if checks
            else ctx.state_at("door", end)
            if ctx.log.coverage.get("door")
            else "unknown"
        )
        if not checks and (
            ctx.has_event("DOOR_CLOSED", entry.timestamp_sec, end)
            or ctx.has_event("HAND_ON_DOOR", entry.timestamp_sec, end)
        ):
            # A possible closing action conflicts with raw state; only a deadline check resolves it.
            state = "unknown"
        if state == "open":
            facts = {**entry.facts, "static_objects": ["door"], "window_end": end}
            if checks:
                facts.update(
                    state_source=checks[0]["source"],
                    state_t=checks[0]["t"],
                    question_id=checks[0]["question_id"],
                    box=checks[0]["box"],
                )
            output.append(
                Finding(
                    "A-DOOR-LOCK",
                    entry.timestamp_sec,
                    facts,
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
            and event.facts.get("from_id") not in session_client_ids(session)
            and event.facts.get("from_role") in {"client", "collector", "visitor", "outsider"}
            and (event.facts.get("to_role") == "cashier" or event.facts.get("to_id") == "desk")
        ):
            output.append(Finding("A-SECOND-PERSON", event.timestamp_sec, event.facts))
    output.extend(
        Finding("A-SECOND-PERSON", event.timestamp_sec, event.facts)
        for event in ctx.events("SECOND_CLIENT_AT_DESK")
    )
    return output


def c_count_before_exit(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("counter") or not ctx.log.coverage.get("roles"):
        return []
    output = []
    for event in ctx.events("SESSION_END"):
        session = ctx.log.sessions.get(str(event.facts["session_id"]))
        if not session or not event.facts.get("confirmed_exit"):
            continue
        counter_events = [
            count
            for count in ctx.log.events
            if count.type in {"COUNT_START", "COUNT_END", "COUNT_INTERRUPTED"}
            and session["start"] <= count.timestamp_sec <= event.timestamp_sec
            and count.facts.get("session_id") == event.facts["session_id"]
        ]
        running = bool(counter_events and counter_events[-1].type == "COUNT_START")
        counted = set(session["counted_cash_ids"])
        count_observed = ctx.has_event(
            "COUNT_END",
            session["start"],
            event.timestamp_sec,
            session_id=event.facts["session_id"],
        )
        if running or (set(session["cash_ids"]) - counted and not count_observed):
            facts = dict(event.facts)
            if running:
                facts.update(
                    count_started=counter_events[-1].timestamp_sec, static_objects=["counter"]
                )
            output.append(Finding("C-COUNT-BEFORE-EXIT", event.timestamp_sec, facts))
    return output


def id_absence_evidence(
    ctx: Context, session_id: str, session: dict, handover: Event
) -> Event | None:
    """Accept an attributed interval observation, never detector misses or negative stills.

    No current still-frame model produces this event. A future interval observer
    must explicitly report ID_NOT_PRESENTED with ok=True, visibility='continuous',
    source, session_id, actor_id and observed_start_sec/observed_end_sec covering
    entry through the first cash handover. Sparse checks cannot be promoted to it.
    """
    start, end = session["start"], handover.timestamp_sec
    for evidence in ctx.events("ID_NOT_PRESENTED"):
        facts = evidence.facts
        observed_start = facts.get("observed_start_sec")
        observed_end = facts.get("observed_end_sec")
        if (
            facts.get("ok") is not True
            or facts.get("visibility") != "continuous"
            or not isinstance(facts.get("source"), str)
            or not facts["source"].strip()
            or facts.get("session_id") != session_id
            or facts.get("actor_id") not in session_client_ids(session)
            or type(observed_start) not in {int, float}
            or type(observed_end) not in {int, float}
            or not isfinite(observed_start)
            or not isfinite(observed_end)
        ):
            continue
        if (
            0 <= observed_start <= start < end <= observed_end
            and observed_end <= evidence.timestamp_sec <= ctx.duration
        ):
            return evidence
    return None


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
        if (
            event.facts.get("from_role") != "client"
            or event.facts.get("from_id") not in session_client_ids(session)
            or not (
                event.facts.get("to_role") == "cashier"
                or event.facts.get("to_id") in {"desk", "counter"}
            )
        ):
            continue
        seen.add(identity)
        shown = any(
            session["start"] <= shown.timestamp_sec <= event.timestamp_sec
            and shown.facts.get("session_id") == identity
            and shown.facts.get("actor_id") in session_client_ids(session)
            for shown in ctx.events("ID_SHOWN")
        )
        evidence = id_absence_evidence(ctx, str(identity), session, event)
        if session["observed_entry"] and not shown and evidence is not None:
            output.append(
                Finding(
                    "C-ID-BEFORE-CASH",
                    event.timestamp_sec,
                    {
                        **event.facts,
                        "id_observation_source": evidence.facts["source"],
                        "observed_start_sec": evidence.facts["observed_start_sec"],
                        "observed_end_sec": evidence.facts["observed_end_sec"],
                    },
                )
            )
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


def seal_check_deliveries(ctx: Context) -> Iterator[tuple[Event, Event, float]]:
    """Observed transfers or a bag appearing during an observed visitor's short departure."""
    transfers = list(collector_transfers(ctx))
    for transfer, exit_event in transfers:
        yield transfer, exit_event, exit_event.timestamp_sec
    if not ctx.log.coverage.get("desk"):
        return
    limit = ctx.rule("K-SEAL-CHECK").min_duration_sec
    assert limit is not None  # collector_transfers validates the codex duration above
    fixtures = [ctx.scene.objects[n].box for n in ("laptop", "counter") if n in ctx.scene.objects]
    bags: dict[str, list[tuple[float, Detection]]] = {}
    for frame in ctx.observations:
        for bag in frame.detections:
            if bag.label == "bag":
                bags.setdefault(bag.track_id, []).append((frame.timestamp_sec, bag))
    for exit_event in ctx.events("EXIT"):
        actor = exit_event.facts.get("actor_id")
        if exit_event.facts.get("role") not in {"client", "visitor", "collector"}:
            continue
        entries = [
            e
            for e in ctx.events("ENTER")
            if e.facts.get("actor_id") == actor
            and e.facts.get("observed_entry")
            and ctx.observations[0].timestamp_sec < e.timestamp_sec < exit_event.timestamp_sec
        ]
        if not entries:
            continue
        entry = entries[-1].timestamp_sec
        for track_id, samples in bags.items():
            on_desk = [
                (t, d)
                for t, d in samples
                if in_zone(ctx.scene, "desk", center(d.box))
                and not any(
                    contains(box, center(d.box), ctx.scene.scaled_distance(0.01))
                    for box in fixtures
                )
            ]
            if not on_desk:
                continue
            appeared, bag = on_desk[0]
            point = center(bag.box)
            if (
                not entry < appeared <= exit_event.timestamp_sec
                or exit_event.timestamp_sec - appeared > limit
                or any(
                    e.facts.get("from_id") == actor and e.facts.get("track_id") == track_id
                    for e, _ in transfers
                )
            ):
                continue
            # A tracker change cannot turn a bag already there into a new delivery.
            if any(
                t <= entry
                and (previous.track_id == track_id or overlap(previous.box, bag.box) > 0.3)
                for history in bags.values()
                for t, previous in history
            ):
                continue
            retained = {
                t
                for t, d in samples
                if exit_event.timestamp_sec <= t <= exit_event.timestamp_sec + LEFT_BEHIND_SEC
                and overlap(d.box, bag.box) > 0.3
            }
            if len(retained) < 2:
                continue
            # A bag may be occluded until accepted. Associate it with a visitor who
            # reached its eventual desk position, using the existing carrying reach.
            reaches = [
                frame.timestamp_sec
                for frame in ctx.observations
                if max(entry, appeared - limit) <= frame.timestamp_sec < exit_event.timestamp_sec
                and any(
                    person.track_id == actor
                    and any(
                        distance(hand, point) < ctx.scene.scaled_distance(0.12)
                        for hand in person.wrists()
                    )
                    for person in frame.detections
                    if person.label == "person"
                )
            ]
            if len(reaches) < 2:
                continue
            arrival = Event(
                type="BAG_ARRIVAL",
                timestamp_sec=appeared,
                facts={
                    "from_id": actor,
                    "object": "bag",
                    "track_id": track_id,
                    "inferred_delivery": True,
                    "visit_start_sec": entry,
                    "bag_appeared_sec": appeared,
                    "last_bag_area_reach_sec": reaches[-1],
                    "window_end": exit_event.timestamp_sec,
                    "confirmed_exit": True,
                },
            )
            yield arrival, exit_event, reaches[-1]


def k_seal_check(ctx: Context) -> list[Finding]:
    output = []
    if not ctx.log.coverage.get("roles") or not ctx.log.coverage.get("hands"):
        return output
    for transfer, exit_event, inspection_end in seal_check_deliveries(ctx):
        if not ctx.has_event(
            "BAG_INSPECTED",
            max(0, transfer.facts.get("visit_start_sec", transfer.timestamp_sec - 1)),
            inspection_end,
            track_id=transfer.facts.get("track_id"),
        ):
            inferred = transfer.type == "BAG_ARRIVAL"
            # An occluded handover has no observed timestamp. Use the first visible
            # bag as evidence, with the confirmed exit ending the window.
            anchor = transfer.timestamp_sec if inferred else exit_event.timestamp_sec
            facts = {**transfer.facts, "exit_sec": exit_event.timestamp_sec}
            if not inferred:
                facts["handover_sec"] = transfer.timestamp_sec
            facts.pop("box", None)
            bag = next(
                (
                    d
                    for d in ctx.nearby(anchor).detections
                    if d.track_id == transfer.facts.get("track_id")
                ),
                None,
            )
            if bag is not None:
                facts["box"] = list(bag.box)
            output.append(Finding("K-SEAL-CHECK", anchor, facts))
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
    "S-NO-MERGE": s_no_merge,
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


def evaluate_rules(ctx: Context, enabled_rule_ids: set[str] | None = None) -> list[Finding]:
    identities = {rule.id for rule in ctx.codex.rules}
    if missing := set(RULES) - identities:
        raise ValueError(f"Required rules absent from codex: {sorted(missing)}")
    output = []
    for identity, function in RULES.items():
        if enabled_rule_ids is not None and identity not in enabled_rule_ids:
            continue
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
