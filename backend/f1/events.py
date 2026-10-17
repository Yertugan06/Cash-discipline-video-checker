"""Build visible events and cash provenance from tracked local-model observations."""

from collections import defaultdict
from dataclasses import dataclass

from backend.f1.calibration import LAPTOP_REACH, behind_glass, in_zone, orient_cashier_side
from backend.f1.vision_types import (
    Detection,
    Event,
    Observation,
    Scene,
    center,
    contains,
    distance,
    worn_or_carried,
)


@dataclass
class PersonHistory:
    first: float
    last: float
    detection: Detection
    origin: tuple[float, float]
    role: str = "visitor"
    announced: bool = False
    exited: bool = False
    observed_entry: bool = False
    moved: float = 0


@dataclass
class CashRecord:
    id: str
    track_id: str
    session_id: str
    location: str
    last: float
    detection: Detection
    first: float = 0.0
    counted: bool = False
    bag_open_seen: bool = False


@dataclass
class EventLog:
    events: list[Event]
    coverage: dict[str, bool]
    warnings: list[str]
    sessions: dict[str, dict]


class StableState:
    def __init__(self, duration: float, unknown_gap: float):
        self.duration = duration
        self.unknown_gap = unknown_gap
        self.current = "unknown"
        self.candidate = "unknown"
        self.since = 0.0
        self.last_known = -100.0

    def push(self, value: str, timestamp: float) -> tuple[str, float] | None:
        if value == "unknown":
            if timestamp - self.last_known > self.unknown_gap:
                self.candidate = "unknown"
                if self.current != "unknown":
                    self.current = "unknown"
                    return "unknown", timestamp
            return None
        self.last_known = timestamp
        if value != self.candidate:
            self.candidate = value
            self.since = timestamp
        if value != self.current and timestamp - self.since + 1e-6 >= self.duration:
            self.current = value
            return value, self.since
        return None


class MoneyFlow:
    def __init__(self):
        self.cash: dict[str, CashRecord] = {}
        self.aliases: dict[str, str] = {}
        self.next_id = 0

    def record(
        self, detection: Detection, timestamp: float, session_id: str
    ) -> tuple[CashRecord, bool]:
        known = self.aliases.get(detection.track_id)
        if known:
            return self.cash[known], False
        candidates = [
            cash
            for cash in self.cash.values()
            if 0 < timestamp - cash.last <= 1.2
            and distance(center(cash.detection.box), center(detection.box)) < 0.12
        ]
        if len(candidates) == 1:
            result = candidates[0]
            self.aliases[detection.track_id] = result.id
            result.track_id = detection.track_id
            return result, True
        self.next_id += 1
        identity = f"cash-{self.next_id}"
        result = CashRecord(
            identity,
            detection.track_id,
            session_id,
            "unknown",
            timestamp,
            detection,
            first=timestamp,
        )
        self.cash[identity] = result
        self.aliases[detection.track_id] = identity
        return result, False


class EventBuilder:
    def __init__(self, scene: Scene, config: dict, fps: float):
        self.scene = scene
        self.config = config
        self.fps = fps
        self.events = []
        self.people: dict[str, PersonHistory] = {}
        self.cashier = ""
        self.sessions: dict[str, dict] = {}
        self.active_session = ""
        self.money = MoneyFlow()
        self.conditions: dict[str, tuple[str, float, dict]] = {}
        self.state_filters = defaultdict(
            lambda: StableState(config["hysteresis_sec"], config["exit_gap_sec"])
        )
        self.state_known = defaultdict(int)
        self.frame_count = 0
        self.hand_frames = 0
        self.id_shown = set()
        self.last_object_location = {}
        self.hand_contacts = {}
        self.counted_cash = []
        self.count_session = ""
        self.count_started = False
        self.bag_contacts = {}
        self.last_personal_presence = {}
        self.last_observation = None

    def emit(self, event_type: str, timestamp: float, **facts) -> None:
        self.events.append(Event(timestamp_sec=max(0, timestamp), type=event_type, facts=facts))

    def condition(self, key: str, kind: str, active: bool, timestamp: float, **facts) -> None:
        if active and key not in self.conditions:
            self.conditions[key] = (kind, timestamp, facts)
            self.emit(kind + "_START", timestamp, condition_id=key, **facts)
        elif not active and key in self.conditions:
            previous, start, old_facts = self.conditions.pop(key)
            self.emit(
                previous + "_END",
                timestamp,
                condition_id=key,
                duration_sec=timestamp - start,
                **old_facts,
            )

    def object_location(self, item: Detection, people: list[Detection]) -> tuple[str, str]:
        point = center(item.box)
        hands = [(distance(point, hand), person) for person in people for hand in person.wrists()]
        if hands:
            gap, owner = min(hands, key=lambda value: value[0])
            if gap <= self.config["hand_distance"]:
                return f"hand:{owner.track_id}", owner.track_id
        for name in ("counter", "safe"):
            if name in self.scene.objects and contains(self.scene.objects[name].box, point, 0.015):
                return name, ""
        for bag in self.current_bags:
            if contains(bag.box, point, 0.01):
                return f"bag:{bag.track_id}", ""
        return ("desk", "") if in_zone(self.scene, "desk", point) else ("unknown", "")

    def role(self, identity: str) -> str:
        person = self.people.get(identity)
        return person.role if person else "unknown"

    def update_people(self, observation: Observation, people: list[Detection]) -> None:
        timestamp = observation.timestamp_sec
        laptop = self.scene.objects.get("laptop")
        for person in people:
            point = person.position()
            if person.track_id not in self.people:
                on_door = in_zone(self.scene, "door", point, 0.05)
                boundary = min(point[0], point[1], 1 - point[0], 1 - point[1]) < 0.12
                self.people[person.track_id] = PersonHistory(
                    timestamp,
                    timestamp,
                    person,
                    point,
                    observed_entry=on_door or (timestamp > 0.4 and boundary),
                )
            history = self.people[person.track_id]
            history.last = timestamp
            history.detection = person
            history.moved = max(history.moved, distance(history.origin, point))
            history.exited = False
        if self.scene.confidence >= 0.3:
            current = self.people.get(self.cashier)
            candidates = []
            for person in people:
                history = self.people[person.track_id]
                state = observation.states.get(person.track_id)
                seated = state is not None and state.value == "seated"
                at_laptop = bool(
                    laptop and any(contains(laptop.box, hand, 0.08) for hand in person.wrists())
                )
                if (
                    in_zone(self.scene, "cashier", person.position())
                    and timestamp - history.first >= 0.6
                ):
                    if seated or at_laptop:
                        candidates.append(person)
            if (
                not current or timestamp - current.last > self.config["exit_gap_sec"]
            ) and candidates:
                anchor = (
                    center(laptop.box)
                    if laptop
                    else tuple(
                        sum(point[i] for point in self.scene.zones["cashier"])
                        / len(self.scene.zones["cashier"])
                        for i in (0, 1)
                    )
                )
                chosen = min(candidates, key=lambda p: distance(center(p.box), anchor))
                self.cashier = chosen.track_id
        for person in people:
            history = self.people[person.track_id]
            previous = history.role
            if person.track_id == self.cashier:
                history.role = "cashier"
            elif history.role != "collector":
                carrying = any(
                    contains(person.box, center(bag.box), 0.03)
                    and not in_zone(self.scene, "desk", center(bag.box))
                    and any(distance(hand, center(bag.box)) < 0.12 for hand in person.wrists())
                    for bag in self.current_bags
                )
                if carrying and timestamp - history.first < 3:
                    history.role = "collector"
                elif in_zone(self.scene, "client", person.position()):
                    history.role = "client"
                elif in_zone(self.scene, "cashier", person.position()):
                    history.role = "outsider"
                else:
                    history.role = "visitor"
            person.role = history.role
            if previous != history.role:
                self.emit(
                    "ROLE",
                    timestamp,
                    actor_id=person.track_id,
                    role=history.role,
                    box=list(person.box),
                )
            if (
                not history.announced
                and timestamp - history.first + 1e-6 >= self.config["hysteresis_sec"]
            ):
                self.emit(
                    "ENTER",
                    history.first,
                    actor_id=person.track_id,
                    role=history.role,
                    observed_entry=history.observed_entry,
                    box=list(person.box),
                )
                history.announced = True
            if history.role == "client" and history.announced and not self.active_session:
                identity = f"session-{len(self.sessions) + 1}"
                self.sessions[identity] = {
                    "client_id": person.track_id,
                    "start": history.first,
                    "end": None,
                    "observed_entry": history.observed_entry,
                    "cash_ids": [],
                    "counted_cash_ids": [],
                }
                self.active_session = identity
                self.emit(
                    "SESSION_START",
                    history.first,
                    session_id=identity,
                    actor_id=person.track_id,
                    observed_entry=history.observed_entry,
                )
                for cash in self.money.cash.values():
                    if not cash.session_id and history.first <= cash.first <= timestamp:
                        cash.session_id = identity
                        self.emit(
                            "CASH_STATE",
                            timestamp,
                            cash_id=cash.id,
                            session_id=identity,
                            location=cash.location,
                            previous_location=cash.location,
                            track_id=cash.track_id,
                            counted=cash.counted,
                            bag_open_seen=cash.bag_open_seen,
                            kind=cash.detection.label,
                            box=list(cash.detection.box),
                        )
        seen = {person.track_id for person in people}
        for identity, history in self.people.items():
            if identity in seen or history.exited or not history.announced:
                continue
            if timestamp - history.last < self.config["exit_gap_sec"]:
                continue
            last_point = history.detection.position()
            door = in_zone(self.scene, "door", last_point, 0.05)
            border = min(last_point[0], last_point[1], 1 - last_point[0], 1 - last_point[1]) < 0.18
            confirmed = door or (border and history.moved > 0.04)
            history.exited = True
            kind = "EXIT" if confirmed else "TRACK_LOST"
            anchor = history.last + 1 / self.fps
            self.emit(
                kind, anchor, actor_id=identity, role=history.role, box=list(history.detection.box)
            )
            if (
                confirmed
                and self.active_session
                and self.sessions[self.active_session]["client_id"] == identity
            ):
                session = self.sessions[self.active_session]
                session["end"] = anchor
                self.emit(
                    "SESSION_END",
                    anchor,
                    session_id=self.active_session,
                    actor_id=identity,
                    confirmed_exit=confirmed,
                    observed_entry=session["observed_entry"],
                )
                self.active_session = ""

    def update_states(self, observation: Observation) -> None:
        timestamp = observation.timestamp_sec
        for name in ("safe", "door", "laptop", "counter"):
            state = observation.states.get(name)
            value = state.value if state else "unknown"
            if value != "unknown":
                self.state_known[name] += 1
            changed = self.state_filters[name].push(value, timestamp)
            if not changed:
                continue
            stable, anchor = changed
            if name in {"safe", "door"}:
                self.emit(
                    name.upper() + "_" + stable.upper(),
                    anchor,
                    state=stable,
                    box=list(self.scene.objects[name].box) if name in self.scene.objects else [],
                )
            elif name == "laptop":
                self.emit(
                    "SCREEN", anchor, state=stable, box=list(self.scene.objects["laptop"].box)
                )
            elif stable == "running":
                cash = [
                    cash.id
                    for cash in self.money.cash.values()
                    if cash.location == "counter" and timestamp - cash.last <= 0.6
                ]
                self.counted_cash = cash
                self.count_session = self.active_session
                self.count_started = True
                self.emit("COUNT_START", anchor, session_id=self.active_session, cash_ids=cash)
            elif stable == "idle" and self.count_started:
                for cash_id in self.counted_cash:
                    record = self.money.cash[cash_id]
                    record.counted = True
                    if record.session_id in self.sessions:
                        self.sessions[record.session_id]["counted_cash_ids"].append(cash_id)
                self.emit(
                    "COUNT_END", anchor, session_id=self.count_session, cash_ids=self.counted_cash
                )
                self.counted_cash = []
                self.count_started = False
            elif stable == "unknown" and self.count_started:
                self.emit("COUNT_INTERRUPTED", anchor, session_id=self.count_session)
                self.counted_cash = []
                self.count_started = False

    def update_objects(self, observation: Observation, people: list[Detection]) -> None:
        timestamp = observation.timestamp_sec
        for item in observation.detections:
            if item.label == "person":
                continue
            location, owner = self.object_location(item, people)
            previous = self.last_object_location.get(item.track_id)
            if item.label in {"cash", "bundle"}:
                record, reassociated = self.money.record(item, timestamp, self.active_session)
                if reassociated:
                    self.emit(
                        "CASH_REASSOCIATED", timestamp, cash_id=record.id, track_id=item.track_id
                    )
                old_location = record.location
                for bag in self.current_bags:
                    bag_state = observation.states.get(bag.track_id)
                    if (
                        contains(bag.box, center(item.box))
                        and bag_state
                        and bag_state.value == "open"
                    ):
                        record.bag_open_seen = True
                if location.startswith("bag:"):
                    bag_state = observation.states.get(location[4:])
                    record.bag_open_seen |= bag_state is not None and bag_state.value == "open"
                if location != "unknown" and (location != old_location or reassociated):
                    self.emit(
                        "CASH_STATE",
                        timestamp,
                        cash_id=record.id,
                        session_id=record.session_id,
                        location=location,
                        previous_location=old_location,
                        track_id=item.track_id,
                        counted=record.counted,
                        bag_open_seen=record.bag_open_seen,
                        kind=item.label,
                        box=list(item.box),
                    )
                    if old_location.startswith("hand:"):
                        sender = old_location[5:]
                        recipient = owner or location
                        if sender != recipient:
                            self.emit(
                                "HANDOVER",
                                timestamp,
                                from_id=sender,
                                to_id=recipient,
                                object=item.label,
                                cash_id=record.id,
                                session_id=self.active_session,
                                track_id=item.track_id,
                                from_role=self.role(sender),
                                to_role=self.role(owner),
                                box=list(item.box),
                            )
                            session = self.sessions.get(self.active_session)
                            if (
                                session
                                and sender == session["client_id"]
                                and record.id not in session["cash_ids"]
                            ):
                                session["cash_ids"].append(record.id)
                record.location = location if location != "unknown" else record.location
                record.last = timestamp
                record.detection = item
            if previous and previous[0].startswith("hand:") and previous[0] != location:
                sender = previous[0][5:]
                if item.label not in {"cash", "bundle"} and location != "unknown":
                    self.emit(
                        "HANDOVER",
                        timestamp,
                        from_id=sender,
                        to_id=owner or location,
                        object=item.label,
                        from_role=self.role(sender),
                        to_role=self.role(owner),
                        session_id=self.active_session,
                        track_id=item.track_id,
                        box=list(item.box),
                    )
            self.last_object_location[item.track_id] = (location, timestamp)
            if item.label in {"id_card", "document"} and owner and self.active_session:
                session = self.sessions[self.active_session]
                if self.role(owner) in {"client", "collector"} or owner == session["client_id"]:
                    key = (self.active_session, item.track_id)
                    if key not in self.id_shown:
                        self.emit(
                            "ID_SHOWN",
                            timestamp,
                            actor_id=owner,
                            session_id=self.active_session,
                            track_id=item.track_id,
                            box=list(item.box),
                        )
                        self.id_shown.add(key)
            if item.label in {"id_card", "document"} and owner and self.role(owner) == "collector":
                key = (owner, item.track_id)
                if key not in self.id_shown:
                    self.emit(
                        "ID_SHOWN",
                        timestamp,
                        actor_id=owner,
                        session_id="",
                        track_id=item.track_id,
                        box=list(item.box),
                    )
                    self.id_shown.add(key)
            if item.label == "bag":
                contacts = [
                    p
                    for p in people
                    if p.role == "cashier"
                    and any(
                        distance(hand, center(item.box)) <= self.config["hand_distance"]
                        for hand in p.wrists()
                    )
                ]
                if contacts:
                    start = self.bag_contacts.setdefault(item.track_id, timestamp)
                    if timestamp - start >= self.config["hysteresis_sec"]:
                        key = ("inspection", item.track_id)
                        if key not in self.id_shown:
                            self.emit(
                                "BAG_INSPECTED",
                                start,
                                track_id=item.track_id,
                                actor_id=contacts[0].track_id,
                                box=list(item.box),
                            )
                            self.id_shown.add(key)
                else:
                    self.bag_contacts.pop(item.track_id, None)

    def push(self, observation: Observation) -> None:
        self.frame_count += 1
        self.last_observation = observation
        timestamp = observation.timestamp_sec
        people = [d for d in observation.detections if d.label == "person"]
        for person in people:
            if behind_glass(self.scene, person.box, self.config["glass_margin"]):
                person.role = "glass"
        people = [person for person in people if person.role != "glass"]
        self.hand_frames += bool(any(person.wrists() for person in people))
        self.current_bags = [d for d in observation.detections if d.label == "bag"]
        self.update_people(observation, people)
        self.update_objects(observation, people)
        self.update_states(observation)
        cashier = next((p for p in people if p.track_id == self.cashier), None)
        history = self.people.get(self.cashier)
        cashier_known = bool(self.cashier)
        cashier_away = bool(history and history.exited)
        if cashier and "laptop" in self.scene.objects:
            # Away = out of reach of the laptop. The old door/zone test fired on a seated
            # cashier whenever the camera faces them (the glass door is right behind them).
            laptop = center(self.scene.objects["laptop"].box)
            cashier_away = distance(cashier.position(), laptop) > LAPTOP_REACH
        self.condition(
            "workstation_away",
            "WORKSTATION_AWAY",
            cashier_known and cashier_away,
            timestamp,
            actor_id=self.cashier,
            role="cashier",
        )
        safe = self.scene.objects.get("safe")
        attended = bool(
            cashier
            and safe
            and (
                contains(safe.box, center(cashier.box), 0.08)
                or any(contains(safe.box, hand, 0.05) for hand in cashier.wrists())
            )
        )
        away_confirmed = cashier is not None or cashier_away
        self.condition(
            "safe_unattended",
            "SAFE_UNATTENDED",
            bool(
                safe
                and cashier_known
                and away_confirmed
                and self.state_filters["safe"].current == "open"
                and not attended
            ),
            timestamp,
            actor_id=self.cashier,
            box=list(safe.box) if safe else [],
        )
        active_conditions = set()
        for person in people:
            if (
                person.role != "cashier"
                and cashier_known
                and in_zone(self.scene, "cashier", person.position())
                and not in_zone(self.scene, "desk", person.position())
            ):
                key = "zone:" + person.track_id
                active_conditions.add(key)
                self.condition(
                    key,
                    "PERSON_IN_CASHIER_ZONE",
                    True,
                    timestamp,
                    actor_id=person.track_id,
                    role=person.role,
                    box=list(person.box),
                )
            for name in ("door", "safe"):
                target = self.scene.objects.get(name)
                if target and any(contains(target.box, hand, 0.025) for hand in person.wrists()):
                    key = (person.track_id, name)
                    previous = self.hand_contacts.get(key, -100)
                    if timestamp - previous > 1:
                        self.emit(
                            "HAND_ON_" + name.upper(),
                            timestamp,
                            actor_id=person.track_id,
                            box=list(target.box),
                        )
                        self.hand_contacts[key] = timestamp
        for item in observation.detections:
            if (
                item.label in {"coat", "handbag"}
                and in_zone(self.scene, "desk", center(item.box))
                and not worn_or_carried(item, people, self.config["hand_distance"])
            ):
                key = "personal:" + item.track_id
                active_conditions.add(key)
                self.condition(
                    key,
                    "PERSONAL_ON_DESK",
                    True,
                    timestamp,
                    track_id=item.track_id,
                    object=item.label,
                    box=list(item.box),
                )
            if item.label in {"cup", "food"}:
                for person in people:
                    if (
                        not person.body
                        or person.body[0][2] < 0.3
                        or any(not 0 <= coordinate <= 1 for coordinate in person.body[0][:2])
                    ):
                        continue
                    head = person.body[0][:2]
                    close = distance(center(item.box), head) < 0.10 and any(
                        distance(hand, center(item.box)) < self.config["hand_distance"]
                        for hand in person.wrists()
                    )
                    at_desk = in_zone(self.scene, "desk", center(person.box), 0.12)
                    if close and at_desk:
                        key = "food:" + person.track_id + ":" + item.track_id
                        active_conditions.add(key)
                        self.condition(
                            key,
                            "FOOD_NEAR_HEAD",
                            True,
                            timestamp,
                            actor_id=person.track_id,
                            track_id=item.track_id,
                            object=item.label,
                            box=list(item.box),
                        )
        for key in list(self.conditions):
            if key.startswith(("zone:", "personal:", "food:")) and key not in active_conditions:
                self.condition(key, "", False, timestamp)

    def finish(self, duration: float) -> EventLog:
        for key in list(self.conditions):
            self.condition(key, "", False, duration)
        counts = {
            name: self.state_known[name] / max(self.frame_count, 1)
            for name in ("safe", "door", "laptop", "counter")
        }
        coverage = {
            "roles": bool(self.cashier) and self.scene.confidence >= 0.3,
            "desk": "desk" in self.scene.objects,
            **{name: name in self.scene.objects and counts[name] >= 0.5 for name in counts},
            "hands": self.hand_frames >= 2,
            "cash": bool(self.money.cash),
        }
        warnings = list(self.scene.warnings)
        if not coverage["roles"]:
            warnings.append(
                "Роль кассира не назначена уверенно; правила, требующие этой роли, отключены."
            )
        if not coverage["cash"]:
            warnings.append(
                "Наличные не распознаны уверенно; проверки движения наличных ограничены."
            )
        if not coverage["hands"]:
            warnings.append(
                "Не хватает уверенных точек рук; передачи предметов могли быть пропущены."
            )
        for name in counts:
            if name in self.scene.objects and not coverage[name]:
                warnings.append(
                    f"Состояние {name} часто неразборчиво; связанные проверки ограничены."
                )
        if any(not session["observed_entry"] for session in self.sessions.values()):
            warnings.append(
                "Есть сессии без наблюдаемого входа; "
                "отсутствие документа до начала записи не оценивается."
            )
        return EventLog(
            sorted(self.events, key=lambda event: event.timestamp_sec),
            coverage,
            warnings,
            self.sessions,
        )


def build_events(
    scene: Scene, observations: list[Observation], config: dict, fps: float, duration: float
) -> EventLog:
    orient_cashier_side(scene, observations, config["glass_margin"])
    builder = EventBuilder(scene, config, fps)
    for observation in observations:
        builder.push(observation)
    return builder.finish(duration)
