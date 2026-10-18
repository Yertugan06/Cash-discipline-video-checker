"""Evidence semantics over numeric observations; these tests do not run model inference."""

from copy import deepcopy

import pytest

from backend.config import ROOT
from backend.f1.events import EventBuilder, MoneyFlow, PersonHistory, build_events
from backend.f1.perception import load_perception_config
from backend.f1.rules import RULES, Context, evaluate_rules
from backend.f1.vision_types import Detection, Observation, State
from tests.test_f1_rules import LEAVE, SESSION, context, event, interval, person_at, requires_cv2


def handover(**updates):
    facts = {
        "session_id": "s1",
        "from_id": "person:2",
        "from_role": "client",
        "to_id": "desk",
        "object": "cash",
        "cash_id": "new-cash",
        "track_id": "new:1",
    }
    return event("HANDOVER", 5, **(facts | updates))


def absence(**updates):
    facts = {
        "session_id": "s1",
        "actor_id": "person:2",
        "ok": True,
        "visibility": "continuous",
        "source": "test:interval-observer",
        "observed_start_sec": 0,
        "observed_end_sec": 5,
    }
    return event("ID_NOT_PRESENTED", 5, **(facts | updates))


def id_context(*evidence):
    return context([handover(), *evidence], deepcopy(SESSION))


def test_context_keeps_legacy_positional_callers_and_optional_visual_records():
    ctx = context()
    legacy = Context(ctx.codex, ctx.log, ctx.observations, ctx.scene, ctx.duration, [])
    assert legacy.desk_objects == [] and legacy.visual_checks is None
    records = [{"family": "id", "answer": "unknown", "ok": False}]
    with_checks = Context(ctx.codex, ctx.log, [], ctx.scene, ctx.duration, None, records)
    assert with_checks.visual_checks is records


def test_a_complete_observed_session_without_an_id_detection_is_unknown():
    ctx = id_context(event("SESSION_END", 10, session_id="s1", confirmed_exit=True))
    assert RULES["C-ID-BEFORE-CASH"](ctx) == []


def test_explicit_continuous_interval_absence_retains_its_evidence_source():
    (finding,) = RULES["C-ID-BEFORE-CASH"](id_context(absence()))
    assert finding.timestamp_sec == 5
    assert finding.facts["id_observation_source"] == "test:interval-observer"
    assert finding.facts["observed_start_sec"] == 0
    assert finding.facts["observed_end_sec"] == 5


@pytest.mark.parametrize(
    "updates",
    [
        {"visibility": "occluded"},
        {"visibility": "sampled"},
        {"visibility": "unknown"},
        {"ok": False},
        {"ok": "true"},
        {"source": ""},
        {"source": " "},
        {"observed_start_sec": 0.5},
        {"observed_start_sec": -1},
        {"observed_end_sec": 4.5},
        {"observed_start_sec": False},
        {"observed_end_sec": "5"},
        {"observed_start_sec": -1, "observed_end_sec": 21},
        {"session_id": "previous-session"},
        {"actor_id": "person:3"},
    ],
)
def test_incomplete_failed_invalid_or_unattributed_absence_is_unknown(updates):
    assert RULES["C-ID-BEFORE-CASH"](id_context(absence(**updates))) == []


@pytest.mark.parametrize(
    "answer,ok",
    [("absent", True), ("no", True), ("unknown", True), ("absent", False), ("present", True)],
)
def test_still_frame_verification_cannot_prove_non_presentation(answer, ok):
    ctx = id_context()
    ctx.visual_checks = [
        {
            "family": "id",
            "t": t,
            "box": [0, 0, 1, 1],
            "answer": answer,
            "ok": ok,
            "source": "test:still-observer",
            "question_id": "id",
        }
        for t in (0, 1, 2, 3, 4, 5)
    ]
    assert RULES["C-ID-BEFORE-CASH"](ctx) == []


@pytest.mark.parametrize(
    "actor,session_id,expected",
    [
        ("person:2", "s1", 0),
        ("person:3", "s1", 1),
        ("person:2", "old", 1),
    ],
)
def test_id_presentation_must_belong_to_this_client_and_session(actor, session_id, expected):
    ctx = id_context(absence(), event("ID_SHOWN", 1, actor_id=actor, session_id=session_id))
    assert len(RULES["C-ID-BEFORE-CASH"](ctx)) == expected


def test_reassociated_client_id_presentation_and_cash_keep_one_session():
    ctx = id_context(
        absence(actor_id="old-client"), event("ID_SHOWN", 1, actor_id="old-client", session_id="s1")
    )
    ctx.log.sessions["s1"]["client_ids"] = ["old-client", "person:2"]
    assert RULES["C-ID-BEFORE-CASH"](ctx) == []


@pytest.mark.parametrize("observed_entry", [False, True])
def test_recording_start_does_not_prove_id_absence(observed_entry):
    ctx = id_context()
    ctx.log.sessions["s1"]["observed_entry"] = observed_entry
    assert RULES["C-ID-BEFORE-CASH"](ctx) == []


def test_second_cash_payment_cannot_repair_an_unknown_first_payment():
    ctx = id_context()
    ctx.log.events.extend(
        [event("HANDOVER", 8, **handover().facts), event("ID_NOT_PRESENTED", 8, **absence().facts)]
    )
    # The late observer's interval starts after the first payment.
    ctx.log.events[-1].facts.update(observed_start_sec=6, observed_end_sec=8)
    assert RULES["C-ID-BEFORE-CASH"](ctx) == []


@requires_cv2
@pytest.mark.parametrize(
    "rule_id,expected",
    [
        ("L-NO-DOCS-ON-LEAVE", 0),
        ("L-PC-LOCKED", 0),
        ("L-NO-CASH-ON-LEAVE", 1),
        ("L-NO-BAG-ON-LEAVE", 1),
    ],
)
def test_equipment_trip_uses_each_rules_departure_scope(rule_id, expected):
    ctx = context([event("SCREEN", 0, state="working"), *interval("WORKSTATION_AWAY", 6)])
    assert len(RULES[rule_id](ctx)) == expected


@requires_cv2
def test_room_exit_anchors_documents_to_the_exit_after_an_equipment_trip():
    ctx = context(
        [
            event("WORKSTATION_AWAY_START", 2, condition_id="away", actor_id="person:1"),
            event("EXIT", 5, actor_id="person:1", role="cashier"),
            event("WORKSTATION_AWAY_END", 10, condition_id="away", actor_id="person:1"),
        ]
    )
    (finding,) = RULES["L-NO-DOCS-ON-LEAVE"](ctx)
    assert finding.timestamp_sec == 5 and finding.facts["confirmed_exit"] is True


@requires_cv2
@pytest.mark.parametrize("role", ["client", "collector", "visitor"])
def test_another_persons_room_exit_does_not_trigger_cashier_leave_rules(role):
    ctx = context([event("SCREEN", 0, state="working"), event("EXIT", 5, role=role)])
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []
    assert RULES["L-PC-LOCKED"](ctx) == []


@requires_cv2
def test_explicitly_unconfirmed_exit_is_unknown_for_room_exit_rules():
    ctx = context(
        [
            event("SCREEN", 0, state="working"),
            event("EXIT", 5, role="cashier", confirmed_exit=False),
        ]
    )
    assert RULES["L-NO-DOCS-ON-LEAVE"](ctx) == []
    assert RULES["L-PC-LOCKED"](ctx) == []


@requires_cv2
@pytest.mark.parametrize("rule_id", ["L-NO-CASH-ON-LEAVE", "L-NO-DOCS-ON-LEAVE"])
def test_room_exit_without_post_exit_observations_cannot_confirm_items_left(rule_id):
    ctx = context(deepcopy(LEAVE))
    ctx.observations = [o for o in ctx.observations if o.timestamp_sec <= 5.5]
    assert RULES[rule_id](ctx) == []


@requires_cv2
def test_no_observations_never_substitutes_a_distant_cash_detection():
    ctx = context(
        [
            event("SESSION_START", 10, session_id="new"),
            event(
                "CASH_STATE", 1, cash_id="old", session_id="s1", location="desk", track_id="cash:1"
            ),
        ]
    )
    ctx.observations = ctx.observations[:1]
    assert RULES["S-CLEAN-DESK-HANDOVER"](ctx) == []
    ctx.observations = []
    assert evaluate_rules(ctx) == []


@requires_cv2
def test_cash_at_clip_cutoff_does_not_imply_a_future_leave_or_storage_failure():
    ctx = context()
    ctx.observations = [
        Observation(timestamp_sec=i / 2, detections=[ctx.observations[0].detections[0]])
        for i in range(8)
    ]
    ctx.duration = 4
    ctx.log = build_events(
        ctx.scene, ctx.observations, load_perception_config(ROOT / "config/perception.yaml"), 2, 4
    )
    assert not ctx.events("SESSION_END") and not ctx.events("EXIT")
    assert evaluate_rules(ctx) == []


def object_builder():
    ctx = context()
    builder = EventBuilder(ctx.scene, load_perception_config(ROOT / "config/perception.yaml"), 2)
    builder.current_bags = []
    builder.sessions = deepcopy(SESSION)
    builder.active_session = "s1"
    for identity, role in [("person:2", "client"), ("person:3", "collector")]:
        person = person_at(0.7, 0.5, identity)
        builder.people[identity] = PersonHistory(0, 0, person, (0.7, 0.5), role=role)
    return builder


@requires_cv2
@pytest.mark.parametrize(
    "label,shown_type",
    [
        ("id_card", "ID_SHOWN"),
        ("document", "DOCUMENT_SHOWN"),
        ("cash", None),
    ],
)
def test_only_an_id_card_can_emit_an_id_presentation(label, shown_type):
    builder = object_builder()
    client = person_at(0.7, 0.5, "person:2")
    client.hands = [(0.6, 0.55, 0.9)]
    item = Detection(label=label, score=0.9, box=(0.58, 0.54, 0.62, 0.56), track_id="item")
    builder.update_objects(Observation(timestamp_sec=1, detections=[item]), [client])
    shown = [e for e in builder.events if e.type.endswith("_SHOWN")]
    assert [e.type for e in shown] == ([shown_type] if shown_type else [])
    if shown:
        assert shown[0].facts["session_id"] == "s1"
        assert shown[0].facts["actor_id"] == "person:2"


@requires_cv2
def test_a_collectors_id_is_not_borrowed_by_the_active_customer_session():
    builder = object_builder()
    collector = person_at(0.7, 0.5, "person:3")
    collector.hands = [(0.6, 0.55, 0.9)]
    card = Detection(label="id_card", score=0.9, box=(0.58, 0.54, 0.62, 0.56), track_id="id")
    builder.update_objects(Observation(timestamp_sec=1, detections=[card]), [collector])
    (shown,) = [e for e in builder.events if e.type == "ID_SHOWN"]
    assert shown.facts["session_id"] == "" and shown.facts["actor_id"] == "person:3"


@requires_cv2
@pytest.mark.parametrize("label", ["cash", "document"])
@pytest.mark.parametrize("gap,expected", [(0.5, 1), (3, 0)])
def test_a_handover_needs_continuous_object_observation(label, gap, expected):
    builder = object_builder()
    client = person_at(0.7, 0.5, "person:2")
    client.hands = [(0.6, 0.55, 0.9)]
    item = Detection(label=label, score=0.9, box=(0.58, 0.54, 0.62, 0.56), track_id="item")
    builder.update_objects(Observation(timestamp_sec=1, detections=[item]), [client])
    builder.update_objects(Observation(timestamp_sec=1 + gap, detections=[item]), [])
    assert len([e for e in builder.events if e.type == "HANDOVER"]) == expected
    if label == "cash":
        latest = [e for e in builder.events if e.type == "CASH_STATE"][-1]
        assert latest.facts["session_id"] == ("s1" if expected else "")


def test_simultaneously_visible_cash_tracks_cannot_be_reassociated():
    money = MoneyFlow()
    old = Detection(label="cash", score=0.9, box=(0.5, 0.5, 0.55, 0.55), track_id="old")
    original, _ = money.record(old, 0, "old-session")
    new = old.model_copy(update={"track_id": "new"})
    current, reassociated = money.record(new, 0.5, "new-session", {"old", "new"})
    assert not reassociated and current.id != original.id
    assert current.session_id == "new-session"


def test_cash_reassociation_is_ambiguous_between_two_prior_objects():
    money = MoneyFlow()
    cash = Detection(label="cash", score=0.9, box=(0.5, 0.5, 0.55, 0.55), track_id="one")
    money.record(cash, 0, "s1")
    money.record(cash.model_copy(update={"track_id": "two"}), 0, "s1")
    record, reassociated = money.record(cash.model_copy(update={"track_id": "three"}), 0.5, "s2")
    assert not reassociated and record.session_id == "s2" and len(money.cash) == 3


def test_untracked_cash_does_not_acquire_a_shared_identity():
    money = MoneyFlow()
    cash = Detection(label="cash", score=0.9, box=(0.5, 0.5, 0.55, 0.55))
    first, _ = money.record(cash, 0, "s1")
    second, reassociated = money.record(cash, 0.5, "s2")
    assert not reassociated and first.id != second.id
    assert money.aliases == {}


def test_a_reappearing_old_alias_cannot_merge_two_visible_cash_objects():
    money = MoneyFlow()
    cash = Detection(label="cash", score=0.9, box=(0.5, 0.5, 0.55, 0.55), track_id="old")
    first, _ = money.record(cash, 0, "s1")
    changed = cash.model_copy(update={"track_id": "replacement"})
    same, reassociated = money.record(changed, 0.5, "s1")
    assert same is first and reassociated
    separate, reassociated = money.record(cash, 0.5, "s2", {"old", "replacement"})
    assert separate.id != first.id and not reassociated


@requires_cv2
def test_short_cash_occlusion_preserves_provenance_without_a_new_session():
    builder = object_builder()
    item = Detection(label="cash", score=0.9, box=(0.58, 0.54, 0.62, 0.56), track_id="one")
    builder.update_objects(Observation(timestamp_sec=1, detections=[item]), [])
    builder.update_objects(Observation(timestamp_sec=1.5, detections=[]), [])
    builder.active_session = "other-session"
    changed = item.model_copy(update={"track_id": "two"})
    builder.update_objects(Observation(timestamp_sec=2, detections=[changed]), [])
    latest = [e for e in builder.events if e.type == "CASH_STATE"][-1]
    assert latest.facts["session_id"] == "s1" and latest.facts["track_id"] == "two"
    assert not any(e.type == "HANDOVER" for e in builder.events)


@requires_cv2
def test_unobserved_video_tail_does_not_extend_an_active_condition():
    ctx = context()
    item = Detection(label="handbag", score=0.9, box=(0.5, 0.6, 0.6, 0.7), track_id="bag")
    frames = [Observation(timestamp_sec=i / 2, detections=[item]) for i in range(4)]
    ctx.log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 20
    )
    ctx.duration = 20
    start, duration = next(ctx.intervals("PERSONAL_ON_DESK"))
    assert start.timestamp_sec == 0 and duration == 2
    (end,) = ctx.events("PERSONAL_ON_DESK_END")
    assert end.facts["end_reason"] == "clip_end"
    assert RULES["W-NO-PERSONAL-ITEMS"](ctx) == []


@requires_cv2
@pytest.mark.parametrize(
    "change,expected",
    [
        ({}, 1),
        ({"to_id": "another-client"}, 0),
        ({"from_id": "stranger"}, 0),
        ({"cash_id": "old-cash"}, 0),
        ({"track_id": "cash:1"}, 0),
    ],
)
def test_cash_coexistence_needs_a_distinct_accepted_payment(change, expected):
    ctx = context(
        [
            event(
                "CASH_STATE",
                1,
                cash_id="old-cash",
                session_id="previous",
                location="desk",
                track_id="cash:1",
            ),
            handover(**change),
        ],
        deepcopy(SESSION),
    )
    findings = RULES["S-NO-MERGE"](ctx)
    assert len(findings) == expected
    if findings:
        assert findings[0].facts["physical_stacking"] == "unknown"
        assert findings[0].facts["mechanism"] == "handover_with_previous_session_cash_visible"


@requires_cv2
def test_storage_before_new_payment_is_a_clean_control_for_cash_coexistence():
    ctx = context(
        [
            event(
                "CASH_STATE",
                1,
                cash_id="old",
                session_id="previous",
                location="desk",
                track_id="cash:1",
            ),
            event(
                "CASH_STATE",
                4,
                cash_id="old",
                session_id="previous",
                location="safe",
                track_id="cash:1",
            ),
            handover(),
        ],
        deepcopy(SESSION),
    )
    assert RULES["S-NO-MERGE"](ctx) == []


@requires_cv2
@pytest.mark.parametrize(
    "ending,expected", [("door", "EXIT"), ("equipment", "TRACK_LOST"), ("occlusion", "TRACK_LOST")]
)
def test_cashier_exit_requires_a_departure_toward_the_room_door(ending, expected):
    ctx = context()
    ctx.scene.objects["door"] = Detection(label="door", score=1, box=(0.8, 0.1, 1, 0.4))
    ctx.scene.zones.update(
        {
            "door": [(0.8, 0.1), (1, 0.1), (1, 0.4), (0.8, 0.4)],
            "cashier": [(0, 0), (1, 0), (1, 1), (0, 1)],
        }
    )
    if ending == "occlusion":
        ctx.scene.zones["door"] = [(0, 0), (0.4, 0), (0.4, 1), (0, 1)]
    destination = {"door": (0.9, 0.3), "equipment": (0.95, 0.8), "occlusion": (0.15, 0.6)}[ending]
    frames = []
    for i in range(15):
        t = i / 2
        cashier = person_at(*(destination if 2 <= t <= 3 else (0.15, 0.6)))
        if t < 2:
            cashier.hands = [(0.3, 0.45, 0.9)]
        frames.append(
            Observation(
                timestamp_sec=t,
                detections=[cashier] if t <= 3 else [],
                states={
                    "person:1": State(
                        value="seated" if t < 2 else "standing", score=0.9, margin=0.8
                    )
                },
            )
        )
    log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 7.5
    )
    departures = [e.type for e in log.events if e.type in {"EXIT", "TRACK_LOST"}]
    assert departures == [expected]


@requires_cv2
def test_lost_cashier_detection_does_not_become_observed_desk_abandonment():
    ctx = context()
    ctx.scene.zones["cashier"] = [(0, 0), (0.5, 0), (0.5, 1), (0, 1)]
    frames = []
    for i in range(20):
        cashier = person_at(0.15, 0.6)
        cashier.hands = [(0.3, 0.45, 0.9)]
        items = [ctx.observations[0].detections[0]]
        frames.append(
            Observation(
                timestamp_sec=i / 2,
                detections=items + ([cashier] if i < 7 else []),
                states={"person:1": State(value="seated", score=0.9, margin=0.8)},
            )
        )
    ctx.observations = frames
    ctx.log = build_events(
        ctx.scene, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 10
    )
    assert ctx.events("TRACK_LOST") and not ctx.events("EXIT")
    assert not ctx.events("WORKSTATION_AWAY_START")
    assert RULES["L-NO-CASH-ON-LEAVE"](ctx) == []


def visual_state(family, sample_t, trigger_type, actor_id="person:1", **updates):
    return {
        "family": family,
        "t": sample_t,
        "box": [0.1, 0.1, 0.9, 0.9],
        "answer": "working" if family == "laptop" else "open",
        "ok": True,
        "source": "test:local-verifier",
        "question_id": family,
        "trigger": trigger_type,
        "trigger_t": 1 if trigger_type == "ENTER" else 5,
        "actor_id": actor_id,
        "observed_entry": trigger_type == "ENTER",
        **updates,
    }


def verified_door_context(**updates):
    ctx = context(
        [
            event("ENTER", 1, actor_id="person:1", observed_entry=True),
            event("DOOR_CLOSED", 2, state="closed"),
            event("HAND_ON_DOOR", 3, actor_id="person:1"),
        ]
    )
    ctx.visual_checks = [visual_state("door", 6, "ENTER", **updates)]
    return ctx


def test_verified_open_deadline_overrides_old_closed_event_and_hand_contact():
    ctx = verified_door_context()
    ctx.log.coverage["door"] = False
    before = list(ctx.log.events)
    (finding,) = RULES["A-DOOR-LOCK"](ctx)
    assert finding.timestamp_sec == 1 and finding.facts["window_end"] == 6
    assert finding.facts["state_source"] == "test:local-verifier"
    assert ctx.log.events == before  # D2-2 owns exact-time event emission.


@pytest.mark.parametrize(
    "updates",
    [
        {"trigger": "scene_start"},
        {"trigger_t": 2},
        {"actor_id": "other"},
        {"observed_entry": False},
        {"t": 1},
        {"ok": False},
        {"source": ""},
        {"answer": "unknown"},
        {"answer": {"open": True}},
        {"box": [0, 0, 2, 1]},
    ],
)
def test_verified_door_requires_actual_trigger_actor_deadline_and_valid_record(updates):
    assert RULES["A-DOOR-LOCK"](verified_door_context(**updates)) == []


@pytest.mark.parametrize("missing", ["entry", "observed_entry"])
def test_verified_door_does_not_create_an_entry(missing):
    ctx = verified_door_context()
    if missing == "entry":
        ctx.log.events = ctx.log.events[1:]
    else:
        ctx.log.events[0].facts["observed_entry"] = False
    assert RULES["A-DOOR-LOCK"](ctx) == []


@pytest.mark.parametrize("answer,expected", [("working", 1), ("locked", 0), ("unknown", 0)])
def test_verified_laptop_needs_readable_state_near_room_exit(answer, expected):
    ctx = context([event("SCREEN", 0, state="working"), *deepcopy(LEAVE)])
    assert RULES["L-PC-LOCKED"](ctx) == []  # An old SCREEN event alone is insufficient.
    ctx.visual_checks = [visual_state("laptop", 5, "EXIT", answer=answer)]
    assert len(RULES["L-PC-LOCKED"](ctx)) == expected
    ctx.visual_checks[0]["t"] = 1
    assert RULES["L-PC-LOCKED"](ctx) == []
    ctx.visual_checks[0]["t"] = 5
    ctx.log.events[-1].type = "WORKSTATION_AWAY_START"
    assert RULES["L-PC-LOCKED"](ctx) == []


@requires_cv2
@pytest.mark.parametrize(
    "samples,expected", [([5, 10], 0), ([5, 5.5, 6], 0), ([5 + i / 2 for i in range(9)], 1)]
)
def test_verified_safe_samples_do_not_invent_open_duration(samples, expected):
    ctx = context([event("HAND_ON_SAFE", 5, actor_id="person:1")])
    ctx.scene.objects["safe"] = Detection(label="safe", score=1, box=(0.8, 0, 1, 0.2))
    cashier = person_at(0.3, 0.6)
    cashier.role = "cashier"
    ctx.observations = [Observation(timestamp_sec=t, detections=[cashier]) for t in samples]
    ctx.visual_checks = [visual_state("safe", t, "HAND_ON_SAFE") for t in samples]
    ctx.log.coverage["safe"] = False
    findings = RULES["S-SAFE-CLOSED"](ctx)
    assert len(findings) == expected
    if findings:
        assert findings[0].facts["duration_sec"] == 4
        ctx.visual_checks[4]["answer"] = "closed"
        assert RULES["S-SAFE-CLOSED"](ctx) == []
        ctx.visual_checks[4]["answer"] = "open"
        cashier.hands = [(0.9, 0.1, 0.9)]
        assert RULES["S-SAFE-CLOSED"](ctx) == []


@pytest.mark.parametrize("actual_exit,expected", [(False, 0), (True, 1)])
def test_verified_safe_needs_visible_unattended_cashier_or_actual_room_exit(actual_exit, expected):
    ctx = context(
        [
            event("HAND_ON_SAFE", 5, actor_id="person:1"),
            event("EXIT" if actual_exit else "TRACK_LOST", 5, role="cashier", actor_id="person:1"),
        ]
    )
    ctx.scene.objects["safe"] = Detection(label="safe", score=1, box=(0.8, 0, 1, 0.2))
    times = [5 + i / 2 for i in range(9)]
    ctx.observations = [Observation(timestamp_sec=t, detections=[]) for t in times]
    ctx.visual_checks = [visual_state("safe", t, "HAND_ON_SAFE") for t in times]
    assert len(RULES["S-SAFE-CLOSED"](ctx)) == expected


@requires_cv2
def test_safe_departure_unknown_breaks_raw_support_at_its_exact_sample():
    ctx = context(
        [
            event("SAFE_UNATTENDED_START", 5, condition_id="safe", actor_id="person:1"),
            event("SAFE_UNATTENDED_END", 9.5, condition_id="safe", actor_id="person:1"),
        ]
    )
    ctx.scene.objects["safe"] = Detection(label="safe", score=1, box=(0.8, 0, 1, 0.2))
    near, away = person_at(0.9, 0.2), person_at(0.3, 0.6)
    near.role = away.role = "cashier"
    times = [4.5 + i / 2 for i in range(11)]
    ctx.observations = [
        Observation(
            timestamp_sec=t,
            detections=[near if t == 4.5 else away],
            states={"safe": State(value="open", score=0.9, margin=0.8)},
        )
        for t in times
    ]
    ctx.visual_checks = [
        visual_state(
            "safe",
            t,
            "safe_open_window",
            parent_trigger="safe_departure",
            window_start=4.5,
            window_end=9.5,
        )
        for t in times
    ]
    before = list(ctx.log.events)
    assert len(RULES["S-SAFE-CLOSED"](ctx)) == 1
    middle = next(check for check in ctx.visual_checks if check["t"] == 7)
    middle["answer"] = "unknown"
    # apply_checks leaves raw CLIP open for unknown; the rule must still break support.
    assert RULES["S-SAFE-CLOSED"](ctx) == []
    middle["t"] = 7.25  # No sampled frame exists here; never move this answer to 7 or 7.5.
    assert len(RULES["S-SAFE-CLOSED"](ctx)) == 1
    assert ctx.log.events == before
