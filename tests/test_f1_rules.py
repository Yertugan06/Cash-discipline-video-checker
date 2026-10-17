import importlib.util
from copy import deepcopy

import pytest

from backend.config import ROOT
from backend.f1.codex import load_codex
from backend.f1.events import EventLog, MoneyFlow, StableState, build_events
from backend.f1.perception import load_perception_config
from backend.f1.rules import RULES, Context, evaluate_rules
from backend.f1.vision_types import Detection, Event, Observation, Scene

HAS_CV2 = importlib.util.find_spec("cv2") is not None
requires_cv2 = pytest.mark.skipif(
    not HAS_CV2,
    reason="opencv-python (cv2) is not installed in this sandbox; backend.f1.calibration.in_zone "
    "needs it. Covered on a machine with opencv-python (see requirements.txt).",
)


def event(event_type, timestamp=5, **facts):
    return Event(type=event_type, timestamp_sec=timestamp, facts=facts)


def context(events=(), sessions=None):
    desk = Detection(label="desk", score=1, box=(0.2, 0.3, 0.8, 0.8))
    laptop = Detection(label="laptop", score=1, box=(0.2, 0.4, 0.4, 0.5))
    scene = Scene(
        objects={"desk": desk, "laptop": laptop},
        confidence=1,
        zones={"desk": [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)]},
    )
    cash = Detection(label="cash", score=0.9, box=(0.55, 0.45, 0.65, 0.55), track_id="cash:1")
    bag = cash.model_copy(update={"label": "bag", "track_id": "bag:1"})
    document = cash.model_copy(update={"label": "document", "track_id": "document:1"})
    coverage = {
        key: True for key in ["roles", "desk", "safe", "door", "laptop", "counter", "hands", "cash"]
    }
    log = EventLog(sorted(events, key=lambda e: e.timestamp_sec), coverage, [], sessions or {})
    return Context(
        load_codex(ROOT / "config" / "f1_codex.yaml"),
        log,
        [Observation(timestamp_sec=i / 2, detections=[cash, bag, document]) for i in range(40)],
        scene,
        20,
    )


LEAVE = [event("EXIT", actor_id="person:1", role="cashier")]
SESSION = {
    "s1": {
        "client_id": "person:2",
        "start": 0,
        "end": 5,
        "observed_entry": True,
        "cash_ids": ["cash-1"],
        "counted_cash_ids": [],
    }
}
COLLECT = [
    event("ENTER", 1, actor_id="person:3", role="collector", observed_entry=True),
    event(
        "HANDOVER",
        5,
        from_id="person:3",
        from_role="collector",
        to_id="desk",
        object="bag",
        track_id="bag:1",
    ),
    event("EXIT", 9, actor_id="person:3", role="collector"),
]


def interval(kind, duration):
    return [
        event(kind + "_START", 2, condition_id="i1", actor_id="person:3"),
        event(kind + "_END", 2 + duration, condition_id="i1"),
    ]


CASES = [
    ("L-NO-CASH-ON-LEAVE", LEAVE, {}),
    ("L-NO-BAG-ON-LEAVE", LEAVE, {}),
    ("L-NO-DOCS-ON-LEAVE", LEAVE, {}),
    ("L-PC-LOCKED", [event("SCREEN", 1, state="working"), *LEAVE], {}),
    ("S-SAFE-CLOSED", interval("SAFE_UNATTENDED", 3.1), {}),
    (
        "S-CLEAN-DESK-HANDOVER",
        [
            event(
                "CASH_STATE",
                1,
                cash_id="cash-1",
                session_id="old",
                location="desk",
                track_id="cash:1",
            ),
            event("SESSION_START", 5, session_id="new", actor_id="person:2"),
        ],
        {},
    ),
    (
        "A-DOOR-LOCK",
        [
            event("ENTER", 1, actor_id="person:1", observed_entry=True),
            event("DOOR_OPEN", 1, state="open"),
        ],
        {},
    ),
    ("A-OUTSIDER-ZONE", interval("PERSON_IN_CASHIER_ZONE", 2.1), {}),
    (
        "A-SECOND-PERSON",
        [
            event(
                "HANDOVER",
                from_id="person:3",
                from_role="client",
                to_id="desk",
                object="document",
                session_id="s1",
            )
        ],
        SESSION,
    ),
    ("C-COUNT-BEFORE-EXIT", [event("SESSION_END", session_id="s1", confirmed_exit=True)], SESSION),
    (
        "C-ID-BEFORE-CASH",
        [event("HANDOVER", from_id="person:2", from_role="client", object="cash", session_id="s1")],
        SESSION,
    ),
    ("K-COLLECTOR-DOC", COLLECT, {}),
    ("K-SEAL-CHECK", COLLECT, {}),
    (
        "K-RECOUNT-BEFORE-SAFE",
        [
            event(
                "CASH_STATE",
                2,
                cash_id="cash-1",
                location="bag:bag:1",
                bag_open_seen=True,
                kind="bundle",
                counted=False,
            ),
            event(
                "CASH_STATE",
                5,
                cash_id="cash-1",
                location="safe",
                bag_open_seen=True,
                kind="bundle",
                counted=False,
            ),
        ],
        {},
    ),
    ("W-NO-PERSONAL-ITEMS", interval("PERSONAL_ON_DESK", 3.1), {}),
    ("W-NO-FOOD", interval("FOOD_NEAR_HEAD", 1), {}),
]


_NEEDS_CV2 = {
    "L-NO-CASH-ON-LEAVE",
    "L-NO-BAG-ON-LEAVE",
    "L-NO-DOCS-ON-LEAVE",
    "L-PC-LOCKED",
    "S-CLEAN-DESK-HANDOVER",
}


@pytest.mark.parametrize("identity,events,sessions", CASES, ids=[case[0] for case in CASES])
def test_each_priority_one_rule_has_a_positive_and_clean_control(identity, events, sessions):
    if identity in _NEEDS_CV2 and not HAS_CV2:
        pytest.skip("evaluate_rules() calls on_desk()/in_zone(), which needs cv2; see requires_cv2")
    ctx = context(deepcopy(events), deepcopy(sessions))
    assert len(RULES[identity](ctx)) == 1
    assert RULES[identity](context()) == []
    findings = evaluate_rules(ctx)
    assert any(f.rule_id == identity for f in findings)


def test_thresholds_and_required_counterevidence():
    assert RULES["S-SAFE-CLOSED"](context(interval("SAFE_UNATTENDED", 3))) == []
    assert RULES["A-OUTSIDER-ZONE"](context(interval("PERSON_IN_CASHIER_ZONE", 2))) == []
    assert RULES["W-NO-PERSONAL-ITEMS"](context(interval("PERSONAL_ON_DESK", 3))) == []
    door = context(CASES[6][1] + [event("HAND_ON_DOOR", 3, actor_id="person:1")])
    assert RULES["A-DOOR-LOCK"](door) == []
    missing_document = context(
        CASES[10][1] + [event("ID_SHOWN", 1, session_id="s1")], deepcopy(SESSION)
    )
    assert RULES["C-ID-BEFORE-CASH"](missing_document) == []
    bootstrap = deepcopy(SESSION)
    bootstrap["s1"]["observed_entry"] = False
    assert RULES["C-ID-BEFORE-CASH"](context(CASES[10][1], bootstrap)) == []
    unfinished = context(
        CASES[9][1] + [event("COUNT_START", 2, session_id="s1")], deepcopy(SESSION)
    )
    assert len(RULES["C-COUNT-BEFORE-EXIT"](unfinished)) == 1
    counted = context(CASES[9][1] + [event("COUNT_END", 2, session_id="s1")], deepcopy(SESSION))
    assert RULES["C-COUNT-BEFORE-EXIT"](counted) == []
    inspected = context(COLLECT + [event("BAG_INSPECTED", 6, track_id="bag:1")])
    assert RULES["K-SEAL-CHECK"](inspected) == []


@pytest.mark.parametrize("recording_start", [0, 2])
@pytest.mark.parametrize("entry_offset,expected_findings", [(0, 0), (1, 1)])
def test_door_requires_an_entry_after_the_first_observation(
    recording_start, entry_offset, expected_findings
):
    ctx = context(
        [
            event(
                "ENTER",
                recording_start + entry_offset,
                actor_id="person:1",
                role="cashier",
                observed_entry=True,
            ),
            event("DOOR_OPEN", recording_start, state="open"),
        ]
    )
    ctx.observations[0].timestamp_sec = recording_start
    assert len(RULES["A-DOOR-LOCK"](ctx)) == expected_findings


def test_hysteresis_and_money_provenance_survive_a_track_change():
    state = StableState(0.6, 1.2)
    assert state.push("open", 0) is None
    assert state.push("closed", 0.2) is None
    assert state.push("open", 0.4) is None
    assert state.push("open", 1.1) == ("open", 0.4)
    money = MoneyFlow()
    first = Detection(label="cash", score=0.9, box=(0.1, 0.1, 0.2, 0.2), track_id="cash:1")
    record, _ = money.record(first, 0, "session-one")
    second = first.model_copy(update={"track_id": "cash:2", "box": (0.12, 0.1, 0.22, 0.2)})
    record2, reassociated = money.record(second, 0.2, "session-two")
    assert reassociated and record2.id == record.id
    assert record2.session_id == "session-one"


@requires_cv2
def test_event_builder_emits_cash_states_without_role_or_identity_invention():
    ctx = context()
    config = load_perception_config(ROOT / "config/perception.yaml")
    observations = [
        Observation(
            timestamp_sec=t,
            detections=[
                Detection(label="cash", score=0.9, box=(0.5, 0.4, 0.6, 0.5), track_id="cash:1")
            ],
        )
        for t in (0, 0.2, 0.4)
    ]
    log = build_events(ctx.scene, observations, config, 5, 1)
    cash = [e for e in log.events if e.type == "CASH_STATE"]
    assert len(cash) == 1 and cash[0].facts["kind"] == "cash"
    assert cash[0].facts["location"] == "desk"
    assert not log.coverage["roles"]


@requires_cv2
def test_client_leaning_and_worn_coat_are_not_zone_or_desk_violations():
    from backend.f1.vision_types import State, worn_or_carried

    ctx = context()
    ctx.scene.zones.update(
        {
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    body_cashier = [(0.0, 0.0, 0.0) for _ in range(17)]
    body_cashier[11] = body_cashier[12] = (0.15, 0.7, 0.9)
    body_client = deepcopy(body_cashier)
    body_client[11] = body_client[12] = (0.75, 0.7, 0.9)
    cashier = Detection(
        label="person",
        score=0.9,
        box=(0.05, 0.1, 0.35, 0.95),
        track_id="person:1",
        body=body_cashier,
    )
    client = Detection(
        label="person", score=0.9, box=(0.25, 0.1, 0.7, 0.95), track_id="person:2", body=body_client
    )
    worn = Detection(label="coat", score=0.9, box=(0.3, 0.2, 0.65, 0.85), track_id="coat:1")
    assert worn_or_carried(worn, [client], 0.07)
    assert not worn_or_carried(
        worn.model_copy(update={"box": (0.55, 0.4, 0.75, 0.6)}), [client], 0.07
    )
    observations = [
        Observation(
            timestamp_sec=i / 5,
            detections=[
                cashier.model_copy(deep=True),
                client.model_copy(deep=True),
                worn.model_copy(deep=True),
            ],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(26)
    ]
    log = build_events(
        ctx.scene, observations, load_perception_config(ROOT / "config/perception.yaml"), 5, 5.2
    )
    assert not any(
        e.type == "PERSON_IN_CASHIER_ZONE_START" and e.facts["actor_id"] == "person:2"
        for e in log.events
    )
    assert not any(e.type == "PERSONAL_ON_DESK_START" for e in log.events)


@requires_cv2
@pytest.mark.parametrize("label", ["laptop", "counter"])
def test_a_workstation_fixture_is_not_a_personal_item(label):
    ctx = context()
    fixture = Detection(label=label, score=0.8, box=(0.5, 0.4, 0.7, 0.5))
    ctx.scene.objects[label] = fixture
    item = fixture.model_copy(update={"label": "handbag", "track_id": "h:1"})
    ctx.observations = [Observation(timestamp_sec=i / 2, detections=[item]) for i in range(9)]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        4.5,
    )
    assert RULES["W-NO-PERSONAL-ITEMS"](ctx) == []


@requires_cv2
@pytest.mark.parametrize("label", ["laptop", "counter"])
@pytest.mark.parametrize("view", ["original", "mirror", "zoom"])
def test_repeated_alternative_fixture_candidates_disambiguate_a_handbag(label, view):
    from scripts.replay_f1 import transform_detection

    ctx = context()
    candidate = Detection(label=label, score=0.2, box=(0.5, 0.4, 0.7, 0.5))
    ctx.scene.candidates = [
        candidate,
        candidate.model_copy(update={"box": (0.501, 0.4, 0.701, 0.501)}),
    ]
    item = candidate.model_copy(update={"label": "handbag", "track_id": "h:1"})

    def point(x, y):
        if view == "mirror":
            return 1 - x, y
        if view == "zoom":
            return 0.5 + (x - 0.5) * 0.6, 0.5 + (y - 0.5) * 0.6
        return x, y

    ctx.scene.objects = {
        name: Detection.model_validate(transform_detection(d.model_dump(), point))
        for name, d in ctx.scene.objects.items()
    }
    ctx.scene.candidates = [
        Detection.model_validate(transform_detection(d.model_dump(), point))
        for d in ctx.scene.candidates
    ]
    ctx.scene.zones = {name: [point(*p) for p in zone] for name, zone in ctx.scene.zones.items()}
    item = Detection.model_validate(transform_detection(item.model_dump(), point))
    ctx.observations = [Observation(timestamp_sec=i / 2, detections=[item]) for i in range(9)]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        4.5,
    )
    assert RULES["W-NO-PERSONAL-ITEMS"](ctx) == []


@requires_cv2
@pytest.mark.parametrize("label", ["coat", "handbag"])
@pytest.mark.parametrize("evidence", ["single_candidate", "partial_overlap", "other_labels"])
def test_a_personal_item_needs_matching_fixture_evidence_to_be_excluded(label, evidence):
    ctx = context()
    item = Detection(label=label, score=0.8, box=(0.5, 0.4, 0.7, 0.5), track_id="item:1")
    candidate = item.model_copy(update={"label": "counter"})
    if evidence == "single_candidate":
        ctx.scene.candidates = [candidate]
    elif evidence == "partial_overlap":
        ctx.scene.objects["counter"] = candidate.model_copy(update={"box": (0.66, 0.4, 0.76, 0.5)})
    else:
        ctx.scene.candidates = [candidate.model_copy(update={"label": "desk"})] * 3
    ctx.observations = [Observation(timestamp_sec=i / 2, detections=[item]) for i in range(9)]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        4.5,
    )
    assert len(RULES["W-NO-PERSONAL-ITEMS"](ctx)) == 1


@requires_cv2
def test_a_handbag_moving_away_from_a_fixture_is_still_a_personal_item():
    ctx = context()
    fixture = Detection(label="counter", score=0.8, box=(0.5, 0.4, 0.7, 0.5))
    ctx.scene.objects["counter"] = fixture
    item = fixture.model_copy(update={"label": "handbag", "track_id": "h:1"})
    moved = item.model_copy(update={"box": (0.5, 0.6, 0.7, 0.7)})
    ctx.observations = [
        Observation(timestamp_sec=i / 2, detections=[item if i < 8 else moved]) for i in range(17)
    ]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        8.5,
    )
    findings = RULES["W-NO-PERSONAL-ITEMS"](ctx)
    assert len(findings) == 1
    assert findings[0].timestamp_sec == 4
    assert findings[0].facts["duration_sec"] == 4.5


@requires_cv2
def test_a_personal_item_stays_on_the_desk_through_a_brief_detection_gap():
    ctx = context()
    item = Detection(label="handbag", score=0.8, box=(0.5, 0.4, 0.7, 0.5), track_id="h:1")
    ctx.observations = [
        Observation(timestamp_sec=i / 2, detections=[] if i == 4 else [item]) for i in range(9)
    ]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        4.5,
    )
    findings = RULES["W-NO-PERSONAL-ITEMS"](ctx)
    assert len(findings) == 1
    assert findings[0].timestamp_sec == 0
    assert findings[0].facts["duration_sec"] == 4.5


@requires_cv2
@pytest.mark.parametrize(
    "ending",
    ["missing", "carried", "carried_after_gap", "off_desk", "off_desk_after_gap", "end_of_video"],
)
def test_personal_item_disappearance_does_not_count_as_time_kept_on_the_desk(ending):
    ctx = context()
    item = Detection(label="handbag", score=0.8, box=(0.5, 0.4, 0.7, 0.5), track_id="h:1")
    ctx.observations = [Observation(timestamp_sec=i / 2, detections=[item]) for i in range(6)]
    for i in range(6, 10):
        detections = []
        if ending.startswith("carried"):
            detections = [
                item,
                Detection(
                    label="person",
                    score=0.9,
                    box=(0.45, 0.2, 0.75, 0.7),
                    track_id="person:1",
                    hands=[(0.6, 0.45, 0.9)],
                ),
            ]
        elif ending.startswith("off_desk"):
            detections = [item.model_copy(update={"box": (0.0, 0.0, 0.1, 0.1)})]
        if ending.endswith("after_gap") and i == 6:
            detections = []
        if ending == "end_of_video" and i > 7:
            break
        ctx.observations.append(Observation(timestamp_sec=i / 2, detections=detections))
    duration = ctx.observations[-1].timestamp_sec + 0.5
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        duration,
    )
    intervals = list(ctx.intervals("PERSONAL_ON_DESK"))
    assert len(intervals) == 1
    assert intervals[0][1] == 3
    assert RULES["W-NO-PERSONAL-ITEMS"](ctx) == []


@requires_cv2
def test_personal_item_intervals_do_not_bridge_a_long_gap_or_a_different_track():
    ctx = context()
    item = Detection(label="handbag", score=0.8, box=(0.5, 0.4, 0.7, 0.5), track_id="h:1")
    other = item.model_copy(update={"track_id": "h:2"})
    ctx.observations = [
        Observation(
            timestamp_sec=i / 2,
            detections=[item] if i < 4 or 8 <= i < 12 else ([other] if 12 <= i < 16 else []),
        )
        for i in range(20)
    ]
    ctx.log = build_events(
        ctx.scene,
        ctx.observations,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        10,
    )
    assert [(e.timestamp_sec, d) for e, d in ctx.intervals("PERSONAL_ON_DESK")] == [
        (0, 2),
        (4, 2),
        (6, 2),
    ]
    assert RULES["W-NO-PERSONAL-ITEMS"](ctx) == []


@requires_cv2
def test_session_tags_initial_cash_and_does_not_end_on_unconfirmed_track_loss():
    from backend.f1.vision_types import State

    ctx = context()
    ctx.scene.zones.update(
        {
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    cashier = Detection(label="person", score=0.9, box=(0.02, 0.2, 0.18, 0.8), track_id="person:1")
    client = Detection(label="person", score=0.9, box=(0.6, 0.2, 0.9, 0.8), track_id="person:2")
    cash = Detection(label="cash", score=0.9, box=(0.5, 0.4, 0.6, 0.5), track_id="cash:1")
    observations = []
    for i in range(17):
        objects = [cashier.model_copy(deep=True), cash.model_copy(deep=True)]
        if i <= 3:
            objects.append(client.model_copy(deep=True))
        observations.append(
            Observation(
                timestamp_sec=i / 5,
                detections=objects,
                states={"person:1": State(value="seated", score=0.9, margin=0.8)},
            )
        )
    log = build_events(
        ctx.scene, observations, load_perception_config(ROOT / "config/perception.yaml"), 5, 3.4
    )
    tagged = [e for e in log.events if e.type == "CASH_STATE" and e.facts["session_id"]]
    assert tagged and tagged[0].facts["session_id"] == "session-1"
    assert any(e.type == "TRACK_LOST" and e.facts["actor_id"] == "person:2" for e in log.events)
    assert not any(e.type == "SESSION_END" for e in log.events)


def test_calibration_takes_the_desk_the_laptop_stands_on(tmp_path):
    from backend.f1.calibration import calibrate

    overrides = tmp_path / "overrides.yaml"
    overrides.write_text("videos: {}\n")
    laptop = Detection(label="laptop", score=0.4, box=(0.5, 0.44, 0.66, 0.53))
    behind_glass = Detection(label="desk", score=0.9, box=(0.3, 0.08, 0.49, 0.11))
    cash_desk = Detection(label="desk", score=0.2, box=(0.05, 0.42, 0.75, 0.6))
    scene = calibrate([laptop, behind_glass, cash_desk], overrides, "0" * 64)
    assert scene.objects["desk"].box == cash_desk.box
    assert scene.candidates == [laptop, behind_glass, cash_desk]
    lonely = calibrate([laptop, behind_glass], overrides, "0" * 64)
    assert "desk" not in lonely.objects and lonely.confidence == 0


@requires_cv2
def test_person_above_the_desk_is_a_glass_reflection_not_an_outsider():
    from backend.f1.vision_types import State

    ctx = context()  # desk (0.2, 0.3, 0.8, 0.8)
    ctx.scene.zones.update(
        {
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    cashier = Detection(label="person", score=0.9, box=(0.02, 0.2, 0.18, 0.8), track_id="person:1")
    reflection = Detection(
        label="person", score=0.8, box=(0.0, 0.1, 0.1, 0.22), track_id="person:2"
    )
    observations = [
        Observation(
            timestamp_sec=i / 5,
            detections=[cashier.model_copy(deep=True), reflection.model_copy(deep=True)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(15)
    ]
    log = build_events(
        ctx.scene, observations, load_perception_config(ROOT / "config/perception.yaml"), 5, 3
    )
    assert not any(e.facts.get("actor_id") == "person:2" for e in log.events)
    assert all(
        d.role == "glass" for o in observations for d in o.detections if d.track_id == "person:2"
    )


def person_at(x, y, track="person:1"):
    body = [(0.0, 0.0, 0.0)] * 17
    body[11] = body[12] = (x, y, 0.9)
    return Detection(
        label="person",
        score=0.9,
        box=(x - 0.1, y - 0.2, x + 0.1, y + 0.1),
        track_id=track,
        body=body,
    )


@requires_cv2
@pytest.mark.parametrize(
    ("second_samples", "waiting", "collector", "expected"),
    [(8, False, False, 1), (1, False, False, 0), (8, True, False, 0), (8, False, True, 0)],
    ids=["served-together", "brief-overlap", "waiting-at-door", "collector"],
)
def test_second_client_requires_sustained_service_at_the_desk(
    second_samples, waiting, collector, expected
):
    from backend.f1.vision_types import State

    ctx = context()
    ctx.scene.zones.update(
        {
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    cashier = person_at(0.15, 0.6)
    client = person_at(0.65, 0.6, "person:2")
    client.hands = [(0.65, 0.5, 0.9)]
    second = person_at(0.85, 0.6, "person:3")
    second.hands = [(0.9, 0.2, 0.9)] if waiting else [(0.76, 0.5, 0.9), (0.85, 0.65, 0.9)]
    bag = Detection(label="bag", score=0.9, box=(0.82, 0.62, 0.88, 0.68), track_id="bag:1")
    frames = []
    for i in range(16):
        detections = [cashier.model_copy(deep=True), client.model_copy(deep=True)]
        if 4 <= i < 4 + second_samples:
            detections.append(second.model_copy(deep=True))
            if collector:
                detections.append(bag.model_copy(deep=True))
        frames.append(
            Observation(
                timestamp_sec=i / 2,
                detections=detections,
                states={"person:1": State(value="seated", score=0.9, margin=0.8)},
            )
        )
    ctx.observations = frames
    ctx.log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 8
    )
    findings = RULES["A-SECOND-PERSON"](ctx)
    assert len(findings) == expected
    if findings:
        assert findings[0].timestamp_sec == 3
        assert findings[0].facts["client_ids"] == ["person:2", "person:3"]


def oriented(desk, laptop, cashier_point, client_point=None, client_frames=4):
    from backend.f1.calibration import orient_cashier_side

    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=desk),
            "laptop": Detection(label="laptop", score=1, box=laptop),
        },
        confidence=1,
    )
    frames = []
    for i in range(10):
        people = [person_at(*cashier_point)]
        if client_point and i < client_frames:  # a client visits for part of the clip
            people.append(person_at(*client_point, track="person:2"))
        frames.append(Observation(timestamp_sec=i / 2, detections=people))
    orient_cashier_side(scene, frames, glass_margin=0.03)
    return scene


def test_cashier_side_is_learned_for_any_camera_angle():
    desk, laptop = (0.05, 0.42, 0.75, 0.6), (0.5, 0.44, 0.66, 0.53)
    # camera over the cashier's shoulder: cashier below the desk centre, client behind the desk
    over_shoulder = oriented(desk, laptop, (0.5, 0.65), client_point=(0.45, 0.45))
    assert over_shoulder.cashier_side((0.5, 0.65)) and not over_shoulder.cashier_side((0.45, 0.45))
    # camera facing the cashier, who stands behind the desk: the split flips
    facing = oriented(desk, laptop, (0.55, 0.4), client_point=(0.45, 0.7))
    assert facing.cashier_side((0.55, 0.4)) and not facing.cashier_side((0.45, 0.7))
    # side view: the desk is tall in the image, so the room splits left/right
    side = oriented((0.4, 0.2, 0.55, 0.8), (0.42, 0.45, 0.5, 0.55), (0.3, 0.5))
    assert side.cashier_direction == (-1.0, 0.0)


@pytest.mark.parametrize(
    ("desk", "laptop", "position", "hand"),
    [
        ((0.1, 0.4, 0.8, 0.6), (0.1, 0.4, 0.25, 0.5), (0.55, 0.7), (0.2, 0.45)),
        ((0.4, 0.1, 0.6, 0.8), (0.4, 0.1, 0.5, 0.25), (0.7, 0.55), (0.45, 0.2)),
    ],
)
def test_cashier_can_reach_a_laptop_at_the_other_end_of_the_desk(desk, laptop, position, hand):
    from backend.f1.calibration import orient_cashier_side

    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=desk),
            "laptop": Detection(label="laptop", score=1, box=laptop),
        },
        confidence=1,
    )
    person = person_at(*position)
    person.hands = [(*hand, 0.9)]
    frames = [
        Observation(timestamp_sec=i / 2, detections=[person.model_copy(deep=True)])
        for i in range(4)
    ]
    orient_cashier_side(scene, frames, 0.03)
    assert scene.confidence == 1
    assert scene.cashier_side(position)


def test_laptop_reach_evidence_keeps_an_established_working_position():
    from backend.f1.calibration import orient_cashier_side

    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=(0.1, 0.4, 0.8, 0.6)),
            "laptop": Detection(label="laptop", score=1, box=(0.45, 0.4, 0.6, 0.5)),
        },
        confidence=1,
    )
    near = person_at(0.5, 0.65)
    reaching = person_at(0.2, 0.7)
    reaching.hands = [(0.5, 0.45, 0.9)]
    frames = [
        Observation(
            timestamp_sec=i / 2,
            detections=[(near if i < 3 else reaching).model_copy(deep=True)],
        )
        for i in range(10)
    ]
    orient_cashier_side(scene, frames, 0.03)
    assert scene.cashier_position == (0.5, 0.65)


@requires_cv2
def test_cashier_working_with_a_distant_laptop_has_to_move_to_leave():
    from backend.f1.vision_types import State

    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=(0.1, 0.4, 0.8, 0.6)),
            "laptop": Detection(label="laptop", score=1, box=(0.1, 0.4, 0.25, 0.5)),
        },
        confidence=1,
    )
    seated = person_at(0.55, 0.7)
    seated.hands = [(0.2, 0.45, 0.9)]
    away = person_at(0.9, 0.95)
    frames = [
        Observation(
            timestamp_sec=i / 2,
            detections=[(seated if i < 6 else away).model_copy(deep=True)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(10)
    ]
    log = build_events(scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 5)
    assert log.coverage["roles"]
    leaves = [e.timestamp_sec for e in log.events if e.type == "WORKSTATION_AWAY_START"]
    assert leaves == [3]


@requires_cv2
@pytest.mark.parametrize("fixture", ["laptop", "counter"])
@pytest.mark.parametrize("contact", ["inside", "outside", "uncertain", "missing"])
def test_a_cashier_reaching_work_equipment_is_not_away(fixture, contact):
    from backend.f1.vision_types import State, center

    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=(0.05, 0.4, 0.95, 0.65)),
            "laptop": Detection(label="laptop", score=1, box=(0.65, 0.4, 0.8, 0.5)),
            "counter": Detection(label="counter", score=1, box=(0.15, 0.4, 0.3, 0.5)),
        },
        confidence=1,
    )
    working, reaching, away = person_at(0.55, 0.52), person_at(0.4, 0.52), person_at(0.1, 0.85)
    x, y = center(scene.objects[fixture].box)
    if contact == "outside":
        y = scene.objects[fixture].box[1] - 0.01
    if contact != "missing":
        reaching.hands = [(x, y, 0.2 if contact == "uncertain" else 0.9)]
    frames = [
        Observation(
            timestamp_sec=i / 2,
            detections=[(working if i < 6 else reaching if i < 10 else away).model_copy(deep=True)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(16)
    ]
    log = build_events(scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 8)
    leaves = [e.timestamp_sec for e in log.events if e.type == "WORKSTATION_AWAY_START"]
    assert leaves == [5 if contact == "inside" else 3]


@pytest.mark.parametrize(
    ("counter_events", "expected"),
    [
        ([event("COUNT_START", 3, session_id="s1")], 1),
        ([event("COUNT_START", 3, session_id="other")], 0),
        ([event("COUNT_START", 3, session_id="s1"), event("COUNT_END", 4, session_id="s1")], 0),
        (
            [
                event("COUNT_START", 3, session_id="s1"),
                event("COUNT_INTERRUPTED", 4, session_id="s1"),
            ],
            0,
        ),
        ([event("COUNT_END", 2, session_id="s1"), event("COUNT_START", 3, session_id="s1")], 1),
    ],
    ids=["running", "other-client", "finished", "unknown", "second-count-running"],
)
def test_running_counter_at_client_exit_is_evidence_even_without_a_cash_box(
    counter_events, expected
):
    sessions = deepcopy(SESSION)
    sessions["s1"]["cash_ids"] = []
    ctx = context(
        [*counter_events, event("SESSION_END", 5, session_id="s1", confirmed_exit=True)],
        sessions,
    )
    assert len(RULES["C-COUNT-BEFORE-EXIT"](ctx)) == expected


@requires_cv2
def test_sitting_client_track_change_preserves_session_and_cash_provenance():
    from backend.f1.vision_types import State

    ctx = context()
    ctx.scene.objects["door"] = Detection(label="door", score=1, box=(0.6, 0.1, 0.95, 0.6))
    ctx.scene.objects["counter"] = Detection(label="counter", score=1, box=(0.2, 0.7, 0.3, 0.8))
    ctx.scene.zones.update(
        {
            "door": [(0.6, 0.1), (0.95, 0.1), (0.95, 0.6), (0.6, 0.6)],
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    cashier = person_at(0.15, 0.6)
    cashier.hands = [(0.3, 0.45, 0.9)]
    frames = []
    for i in range(16):
        t = i / 2
        detections = [cashier.model_copy(deep=True)]
        if 1 <= t <= 3.5:
            client = (
                person_at(0.75, 0.25, "person:2") if t < 2.5 else person_at(0.7, 0.5, "person:2")
            )
            client.hands = [(0.65, 0.52, 0.9)]
            detections.append(client)
        elif t >= 5:
            client = person_at(0.7, 0.55, "person:3")
            client.hands = [(0.64, 0.5, 0.9)]
            detections.append(client)
        if 2.5 <= t <= 3.5 or t >= 7:
            x, y = (0.65, 0.52) if t < 7 else (0.3, 0.45)
            detections.append(
                Detection(
                    label="cash",
                    score=0.9,
                    box=(x - 0.02, y - 0.01, x + 0.02, y + 0.01),
                    track_id="cash:1",
                )
            )
        frames.append(
            Observation(
                timestamp_sec=t,
                detections=detections,
                states={
                    "person:1": State(value="seated", score=0.9, margin=0.8),
                    "counter": State(value="running" if t >= 2 else "idle", score=0.9, margin=0.8),
                },
            )
        )
    ctx.observations = frames
    ctx.log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 8
    )
    assert len(ctx.log.sessions) == 1
    session = ctx.log.sessions["session-1"]
    assert session["client_id"] == "person:3"
    assert session["client_ids"] == ["person:2", "person:3"]
    assert session["cash_ids"] == ["cash-1"]
    assert not any(e.type == "SESSION_END" for e in ctx.log.events)
    assert RULES["C-COUNT-BEFORE-EXIT"](ctx) == []
    assert [f.timestamp_sec for f in RULES["C-ID-BEFORE-CASH"](ctx)] == [7]
    assert RULES["A-SECOND-PERSON"](ctx) == []


@requires_cv2
def test_returning_client_track_starts_after_its_confirmed_exit():
    from backend.f1.vision_types import State

    ctx = context()
    ctx.scene.zones.update(
        {
            "door": [(0.6, 0), (0.9, 0), (0.9, 0.3), (0.6, 0.3)],
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    frames = []
    for i in range(18):
        t = i / 2
        detections = [person_at(0.15, 0.6)]
        if 1 <= t <= 3 or t >= 6:
            y = 0.55 if t < 3 else 0.2
            detections.append(person_at(0.75, y, "person:2"))
        frames.append(
            Observation(
                timestamp_sec=t,
                detections=detections,
                states={"person:1": State(value="seated", score=0.9, margin=0.8)},
            )
        )
    log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 9
    )
    assert [(s["start"], s["end"]) for s in log.sessions.values()] == [(1, 3.5), (6, None)]


@requires_cv2
def test_a_lost_client_cannot_own_a_later_distinct_client_session():
    from backend.f1.vision_types import State

    ctx = context()
    ctx.scene.zones.update(
        {
            "cashier": [(0, 0), (0.5, 0), (0.5, 1), (0, 1)],
            "client": [(0.5, 0), (1, 0), (1, 1), (0.5, 1)],
        }
    )
    frames = []
    for i in range(16):
        t = i / 2
        detections = [person_at(0.15, 0.6)]
        if 1 <= t <= 2.5:
            detections.append(person_at(0.7, 0.55, "person:2"))
        elif t >= 5:
            detections.append(person_at(0.7, 0.55, "person:3"))
        frames.append(
            Observation(
                timestamp_sec=t,
                detections=detections,
                states={"person:1": State(value="seated", score=0.9, margin=0.8)},
            )
        )
    log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 8
    )
    assert [(s["client_id"], s["start"], s["end"]) for s in log.sessions.values()] == [
        ("person:2", 1, 3),
        ("person:3", 5, None),
    ]
    assert len([e for e in log.events if e.type == "SESSION_LOST"]) == 1
    assert not any(e.type == "SESSION_END" for e in log.events)


def test_a_client_nearer_the_laptop_does_not_flip_the_cashier_side():
    # laptop at the desk's end: during service the client is closer to it than the cashier,
    # but only the cashier is ever alone at the workstation
    desk, laptop = (0.1, 0.45, 0.76, 0.57), (0.13, 0.42, 0.29, 0.52)
    scene = oriented(desk, laptop, (0.4, 0.62), client_point=(0.3, 0.44), client_frames=7)
    assert scene.cashier_side((0.4, 0.62)) and not scene.cashier_side((0.3, 0.44))


def test_cashier_side_stays_unknown_when_nobody_works_at_the_laptop():
    scene = oriented((0.05, 0.42, 0.75, 0.6), (0.5, 0.44, 0.66, 0.53), (0.05, 0.05))
    assert "cashier" not in scene.zones and scene.confidence == 0
    assert scene.warnings


@requires_cv2
def test_the_laptop_seen_as_a_tablet_is_not_left_on_the_desk():
    from backend.f1.rules import l_no_docs_on_leave

    ctx = context(deepcopy(LEAVE))
    on_laptop = Detection(label="tablet", score=0.5, box=(0.22, 0.41, 0.38, 0.49), track_id="t:9")
    ctx.observations = [
        Observation(timestamp_sec=i / 2, detections=[on_laptop]) for i in range(10, 19)
    ]
    assert not l_no_docs_on_leave(ctx)


@requires_cv2
@pytest.mark.parametrize(("picked_up", "expected"), [(True, 0), (False, 1)])
def test_an_item_counts_as_left_only_if_still_there_after_the_cashier_walks_off(
    picked_up, expected
):
    from backend.f1.rules import l_no_docs_on_leave

    ctx = context(deepcopy(LEAVE))
    document = Detection(label="document", score=0.5, box=(0.55, 0.45, 0.65, 0.55), track_id="d:1")
    later = [] if picked_up else [document]
    ctx.observations = [
        Observation(timestamp_sec=i / 2, detections=[document] if i < 14 else later)
        for i in range(10, 19)
    ]
    assert len(l_no_docs_on_leave(ctx)) == expected


@requires_cv2
@pytest.mark.parametrize(
    "identity", ["L-NO-CASH-ON-LEAVE", "L-NO-DOCS-ON-LEAVE", "L-NO-BAG-ON-LEAVE"]
)
@pytest.mark.parametrize("missing", [{5}, {7}, {5, 7}])
def test_leave_items_survive_missing_detections_at_the_exact_check_times(identity, missing):
    ctx = context(deepcopy(LEAVE))
    for frame in ctx.observations:
        if frame.timestamp_sec in missing:
            frame.detections = []
        elif frame.timestamp_sec == 8.5:
            frame.detections = [d.model_copy(update={"score": 0.4}) for d in frame.detections]
    findings = RULES[identity](ctx)
    assert len(findings) == 1
    assert findings[0].timestamp_sec == 5
    assert findings[0].confidence == 0.4  # Include confidence from the later evidence window.


@requires_cv2
@pytest.mark.parametrize("timestamps", [[5, 7], [0], [5, 5, 7, 7]])
def test_leave_evidence_needs_repeated_observations_in_each_bounded_window(timestamps):
    ctx = context(deepcopy(LEAVE))
    items = ctx.observations[0].detections
    ctx.observations = [Observation(timestamp_sec=t, detections=items) for t in timestamps]
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []


@requires_cv2
def test_leave_evidence_does_not_count_one_nearby_detection_for_two_observations():
    ctx = context(deepcopy(LEAVE))
    items = ctx.observations[0].detections
    ctx.observations = [
        Observation(timestamp_sec=t, detections=items if detected else [])
        for t, detected in [(5, False), (5.3, True), (7, False), (7.3, True)]
    ]
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []


@requires_cv2
def test_item_leave_requires_the_cashier_to_remain_away_for_the_confirmation_delay():
    ctx = context(interval("WORKSTATION_AWAY", 1))
    assert ctx.leaves()  # Other leave rules keep their existing departure semantics.
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []


@requires_cv2
def test_a_short_away_interval_does_not_hide_a_following_sustained_departure():
    ctx = context(
        [
            event("WORKSTATION_AWAY_START", 5, condition_id="away", actor_id="person:1"),
            event("WORKSTATION_AWAY_END", 6, condition_id="away"),
            event("WORKSTATION_AWAY_START", 6.5, condition_id="away", actor_id="person:1"),
            event("WORKSTATION_AWAY_END", 10.5, condition_id="away"),
        ]
    )
    assert [f.timestamp_sec for f in RULES["L-NO-DOCS-ON-LEAVE"](ctx)] == [6.5]


@requires_cv2
def test_an_item_is_not_confirmed_left_if_the_recording_ends_before_the_later_window():
    ctx = context(deepcopy(LEAVE))
    ctx.duration = 6.5
    ctx.observations = [o for o in ctx.observations if o.timestamp_sec < ctx.duration]
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []


@requires_cv2
def test_a_seated_cashier_in_front_of_the_glass_door_is_not_away():
    from backend.f1.vision_types import State

    # camera facing the cashier: the door is right behind them in the image
    door = Detection(label="door", score=1, box=(0.0, 0.0, 0.4, 0.55))
    ctx = context()
    ctx.scene.objects["door"] = door
    ctx.scene.zones.update(
        {
            "door": [(0.0, 0.0), (0.4, 0.0), (0.4, 0.55), (0.0, 0.55)],
            "cashier": [(0, 0), (1, 0), (1, 0.45), (0, 0.45)],
            "client": [(0, 0.45), (1, 0.45), (1, 1), (0, 1)],
        }
    )
    seated, walked_off = person_at(0.12, 0.4), person_at(0.75, 0.25)
    observations = [
        Observation(
            timestamp_sec=i / 2,
            detections=[(seated if i < 10 else walked_off).model_copy(deep=True)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(16)
    ]
    log = build_events(
        ctx.scene, observations, load_perception_config(ROOT / "config/perception.yaml"), 2, 8
    )
    away = [e.timestamp_sec for e in log.events if e.type == "WORKSTATION_AWAY_START"]
    assert away == [5.0]


@requires_cv2
def test_a_cash_bag_left_on_the_desk_is_cash_left_unattended():
    ctx = context(deepcopy(LEAVE))
    for frame in ctx.observations:
        frame.detections = [d for d in frame.detections if d.label == "bag"]
    findings = RULES["L-NO-CASH-ON-LEAVE"](ctx)
    assert [f.facts["track_ids"] for f in findings] == [["bag:1"]]
