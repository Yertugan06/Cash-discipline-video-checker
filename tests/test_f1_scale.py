"""Synthetic geometry checks, independent of the labelled clips and camera distance."""

import importlib.util

import pytest

from backend.config import ROOT
from backend.f1.calibration import behind_glass, calibrate, orient_cashier_side
from backend.f1.codex import load_codex
from backend.f1.events import EventBuilder, EventLog, PersonHistory, build_events
from backend.f1.perception import load_perception_config
from backend.f1.rules import Context
from backend.f1.vision_types import Detection, Observation, Scene, State
from scripts.replay_f1 import transform_detection

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("cv2") is None, reason="F1 geometry needs opencv-python"
)


@pytest.fixture(params=[(z, tall) for z in (0.8, 1.0, 1.2) for tall in (False, True)])
def view(request):
    zoom, tall = request.param

    def point(x, y):
        x, y = 0.5 + (x - 0.5) * zoom, 0.5 + (y - 0.5) * zoom
        return (y, x) if tall else (x, y)

    return point


def item(label, box, track=None):
    return Detection(label=label, score=0.9, box=box, track_id=track or label + ":1")


def person(x, y, *, hands=(), track="person:1"):
    body = [(0.0, 0.0, 0.0)] * 17
    body[11] = body[12] = (x, y, 0.9)
    return Detection(
        label="person",
        score=0.9,
        box=(x - 0.06, y - 0.12, x + 0.06, y + 0.12),
        body=body,
        hands=[(*hand, 0.9) for hand in hands],
        track_id=track,
    )


def scene():
    objects = {
        "desk": item("desk", (0.15, 0.4, 0.85, 0.6)),
        "laptop": item("laptop", (0.55, 0.4, 0.7, 0.5)),
        "counter": item("counter", (0.25, 0.43, 0.35, 0.53)),
        "safe": item("safe", (0.15, 0.2, 0.25, 0.39)),
        "door": item("door", (0.3, 0.2, 0.4, 0.4)),
    }
    zones = {
        name: [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        for name, d in objects.items()
        for x1, y1, x2, y2 in [d.box]
    }
    zones["cashier"] = [(0, 0.5), (1, 0.5), (1, 1), (0, 1)]
    zones["client"] = [(0, 0), (1, 0), (1, 0.5), (0, 0.5)]
    return Scene(objects=objects, zones=zones, confidence=1)


def moved(detection, view):
    return Detection.model_validate(transform_detection(detection.model_dump(), view))


def moved_scene(source, view):
    result = source.model_copy(deep=True)
    result.objects = {k: moved(d, view) for k, d in source.objects.items()}
    result.zones = {k: [view(x, y) for x, y in polygon] for k, polygon in source.zones.items()}
    if source.cashier_position is not None:
        result.cashier_position = view(*source.cashier_position)
    return result


def builder(view):
    result = EventBuilder(
        moved_scene(scene(), view), load_perception_config(ROOT / "config/perception.yaml"), 2
    )
    result.current_bags = []
    return result


def test_scene_reference_and_unknown_scale_are_explicit():
    assert scene().scaled_distance(0.07) == pytest.approx(0.07)
    assert Scene(objects={}).scaled_distance(0.07) == 0.07


@pytest.mark.parametrize("gap", [0.018, 0.023])
def test_desk_selection_scales_the_laptop_containment_margin(view, tmp_path, gap):
    desk = item("desk", (0.15, 0.4, 0.85, 0.6))
    laptop = item("laptop", (0.55, 0.35 - gap, 0.7, 0.45 - gap))
    other = item("desk", (0.52, 0.3, 0.72, 0.43))
    other.score = 0.5
    candidates = [moved(d, view) for d in (desk, laptop, other)]
    overrides = tmp_path / "overrides.yaml"
    overrides.write_text("videos: {}\n")
    calibrated = calibrate(candidates, overrides, "0" * 64)
    expected = desk if gap < 0.02 else other
    assert calibrated.objects["desk"].box == pytest.approx(moved(expected, view).box)


@pytest.mark.parametrize(("gap", "reflection"), [(0.028, False), (0.034, True)])
def test_glass_clearance_scales_with_the_desk(view, gap, reflection):
    s = moved_scene(scene(), view)
    x1, y1, x2, y2 = s.objects["desk"].box
    # Place the feet above the vertical far edge in either image orientation.
    _, bottom = view(0.15 - gap, 0.5) if y2 - y1 > x2 - x1 else view(0.5, 0.4 - gap)
    p = item("person", (0.3, bottom - 0.05, 0.4, bottom))
    assert behind_glass(s, p.box, 0.03) is reflection


def test_laptop_reach_preserves_the_cashier_anchor_and_leave_time(view):
    s = scene()
    s.zones = {k: v for k, v in s.zones.items() if k not in {"cashier", "client"}}
    s = moved_scene(s, view)
    working, away = (moved(person(0.625, y), view) for y in (0.69, 0.73))
    frames = [
        Observation(
            timestamp_sec=i / 2,
            detections=[(working if i < 6 else away).model_copy(deep=True)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(12)
    ]
    log = build_events(s, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 6)
    assert s.cashier_position == pytest.approx(view(0.625, 0.69))
    assert log.coverage["roles"]
    assert [e.timestamp_sec for e in log.events if e.type == "WORKSTATION_AWAY_START"] == [3]


@pytest.mark.parametrize(("gap", "known"), [(0.075, True), (0.09, False)])
def test_laptop_hand_margin_can_locate_a_distant_cashier(view, gap, known):
    s = scene()
    s.zones = {}
    s = moved_scene(s, view)
    cashier = moved(person(0.3, 0.65, hands=[(0.55 - gap, 0.45)]), view)
    frames = [Observation(timestamp_sec=i / 2, detections=[cashier]) for i in range(4)]
    orient_cashier_side(s, frames, 0.03)
    assert (s.cashier_position is not None) is known
    # Assignment at a manually calibrated workstation uses the same hand margin.
    log = build_events(
        moved_scene(scene(), view),
        frames,
        load_perception_config(ROOT / "config/perception.yaml"),
        2,
        2,
    )
    assert log.coverage["roles"] is known


def test_a_distant_learned_workstation_anchor_scales_too(view):
    s = scene()
    s.cashier_position = (0.34, 0.55)
    s = moved_scene(s, view)
    frames = [
        Observation(
            timestamp_sec=i / 2,
            detections=[moved(person(*((0.34, 0.55) if i < 6 else (0.58, 0.68))), view)],
            states={"person:1": State(value="seated", score=0.9, margin=0.8)},
        )
        for i in range(12)
    ]
    log = build_events(s, frames, load_perception_config(ROOT / "config/perception.yaml"), 2, 6)
    assert [e.timestamp_sec for e in log.events if e.type == "WORKSTATION_AWAY_START"] == [3]


@pytest.mark.parametrize(("gap", "serving"), [(0.065, True), (0.08, False)])
def test_waiting_and_served_clients_keep_their_meaning_under_zoom(view, gap, serving):
    b = builder(view)
    clients = [
        moved(person(0.45, 0.35, hands=[(0.45, 0.45)], track="client:1"), view),
        moved(person(0.6, 0.35, hands=[(0.6, 0.4 - gap)], track="client:2"), view),
    ]
    for p in clients:
        p.role = "client"
        b.people[p.track_id] = PersonHistory(0, 0, p, p.position(), role="client", announced=True)
    b.active_session = "s1"
    b.sessions["s1"] = {"client_id": "client:1"}
    for t in (0, 0.5, 1):
        b.update_client_service(t, clients)
    assert any(e.type == "SECOND_CLIENT_AT_DESK" for e in b.events) is serving


@pytest.mark.parametrize(("gap", "held"), [(0.065, True), (0.08, False)])
def test_cash_location_bag_inspection_and_carried_items_share_scene_hand_distance(view, gap, held):
    b = builder(view)
    p = moved(person(0.45, 0.65, hands=[(0.45 + gap, 0.55)]), view)
    p.role = "cashier"
    cash = moved(item("cash", (0.44, 0.54, 0.46, 0.56)), view)
    assert b.object_location(cash, [p])[0] == ("hand:person:1" if held else "desk")
    bag = cash.model_copy(update={"label": "bag", "track_id": "bag:1"})
    for t in (0, 0.5, 1):
        b.update_objects(Observation(timestamp_sec=t, detections=[bag]), [p])
    assert any(e.type == "BAG_INSPECTED" for e in b.events) is held
    handbag = bag.model_copy(update={"label": "handbag", "track_id": "handbag:1"})
    b.push(Observation(timestamp_sec=2, detections=[p, handbag]))
    assert any(e.type == "PERSONAL_ON_DESK_START" for e in b.events) is not held


@pytest.mark.parametrize("target", ["counter", "safe", "bag"])
@pytest.mark.parametrize("inside_margin", [True, False])
def test_object_location_uses_scene_relative_fixture_and_bag_margins(view, target, inside_margin):
    b = builder(view)
    box = scene().objects[target].box if target != "bag" else (0.4, 0.45, 0.5, 0.55)
    margin = 0.01 if target == "bag" else 0.015
    gap = margin * (0.9 if inside_margin else 1.1)
    cash = moved(item("cash", (box[2] + gap - 0.005, 0.49, box[2] + gap + 0.005, 0.51)), view)
    if target == "safe":
        cash = moved(item("cash", (box[2] + gap - 0.005, 0.29, box[2] + gap + 0.005, 0.31)), view)
    if target == "bag":
        b.current_bags = [moved(item("bag", box), view)]
    location = b.object_location(cash, [])[0]
    assert (location == ("bag:bag:1" if target == "bag" else target)) is inside_margin


@pytest.mark.parametrize(("gap", "same_cash"), [(0.11, True), (0.14, False)])
def test_cash_reassociation_scales_its_motion_limit(view, gap, same_cash):
    b = builder(view)
    first = moved(item("cash", (0.4, 0.48, 0.42, 0.5)), view)
    second = moved(item("cash", (0.4 + gap, 0.48, 0.42 + gap, 0.5), "cash:2"), view)
    record, _ = b.money.record(first, 0, "old")
    next_record, reassociated = b.money.record(second, 0.5, "new")
    assert reassociated is same_cash
    assert (record.id == next_record.id) is same_cash


@pytest.mark.parametrize("cause", ["wrist", "fixture"])
@pytest.mark.parametrize("close", [True, False])
def test_leave_items_exclude_held_objects_and_fixtures_at_every_scale(view, cause, close):
    s = moved_scene(scene(), view)
    gap = (0.043 if close else 0.05) if cause == "wrist" else (0.009 if close else 0.012)
    if cause == "wrist":
        document = item("document", (0.44, 0.54, 0.46, 0.56))
        people = [person(0.45, 0.65, hands=[(0.45 + gap, 0.55)])]
    else:
        document = item("document", (0.7 + gap - 0.002, 0.44, 0.7 + gap + 0.002, 0.46))
        people = []
    frame = Observation(timestamp_sec=0, detections=[moved(d, view) for d in [document, *people]])
    ctx = Context(
        load_codex(ROOT / "config/f1_codex.yaml"), EventLog([], {}, [], {}), [frame], s, 1
    )
    assert bool(ctx.items_on_desk(frame, {"document"})) is not close


@pytest.mark.parametrize("contact", ["body", "hand", "door", "safe"])
@pytest.mark.parametrize("close", [True, False])
def test_safe_attendance_and_fixture_contacts_scale_with_the_scene(view, contact, close):
    b = builder(view)
    target = scene().objects["door" if contact == "door" else "safe"].box
    margin = {"body": 0.08, "hand": 0.05, "door": 0.025, "safe": 0.025}[contact]
    gap = margin * (0.9 if close else 1.1)
    if contact == "body":
        p = person(target[2] + gap, 0.3)
    else:
        p = person(0.65, 0.65, hands=[(target[2] + gap, 0.3)])
    p = moved(p, view)
    b.cashier = p.track_id
    b.people[p.track_id] = PersonHistory(0, 0, p, p.position(), role="cashier", announced=True)
    b.state_filters["safe"].current = "open"
    b.push(
        Observation(
            timestamp_sec=0, detections=[p], states={"safe": State(value="open", score=1, margin=1)}
        )
    )
    if contact in {"body", "hand"}:
        assert any(e.type == "SAFE_UNATTENDED_START" for e in b.events) is not close
    else:
        assert any(e.type == "HAND_ON_" + contact.upper() for e in b.events) is close


@pytest.mark.parametrize("cause", ["head", "wrist", "desk"])
@pytest.mark.parametrize("close", [True, False])
def test_food_proximity_uses_the_same_scene_metric(view, cause, close):
    b = builder(view)
    gap = {"head": 0.1, "wrist": 0.07, "desk": 0.12}[cause] * (0.9 if close else 1.1)
    food = item("food", (0.44, 0.34, 0.46, 0.36))
    p = person(0.45, 0.5 if cause != "desk" else 0.4 - gap, hands=[(0.45, 0.35)])
    p.body[0] = (0.45 - gap if cause == "head" else 0.45, 0.35, 0.9)
    if cause == "wrist":
        p.hands = [(0.45 + gap, 0.35, 0.9)]
    b.push(Observation(timestamp_sec=0, detections=[moved(d, view) for d in (p, food)]))
    assert any(e.type == "FOOD_NEAR_HEAD_START" for e in b.events) is close


@pytest.mark.parametrize("cause", ["hand", "person_box"])
@pytest.mark.parametrize("close", [True, False])
def test_collector_carrying_checks_scale_with_the_person_and_bag(view, cause, close):
    b = builder(view)
    gap = (0.11 if close else 0.14) if cause == "hand" else (0.028 if close else 0.034)
    bag = item("bag", (0.09, 0.49, 0.11, 0.51))
    p = person(0.2, 0.45, hands=[(0.1 + gap if cause == "hand" else 0.1, 0.5)])
    p.box = (0.1 + (gap if cause == "person_box" else 0), 0.33, 0.26, 0.57)
    b.push(Observation(timestamp_sec=0, detections=[moved(d, view) for d in (p, bag)]))
    assert (b.people[p.track_id].role == "collector") is close


@pytest.mark.parametrize(("motion", "confirmed"), [(0.045, True), (0.038, False)])
@pytest.mark.parametrize("at_door", [True, False])
def test_departure_motion_is_relative_to_the_desk(view, motion, confirmed, at_door):
    b = builder(view)
    for i in range(8):
        if at_door:
            p = person(0.35, 0.36 - (motion if i >= 2 else 0))
        else:
            p = person(0.95 - (motion if i < 2 else 0), 0.5)
            b.scene.zones.pop("cashier", None)
            b.scene.zones.pop("client", None)
        people = [moved(p, view)] if i < 3 else []
        b.update_people(Observation(timestamp_sec=i / 2, detections=people), people)
    assert any(e.type == "EXIT" for e in b.events) is confirmed
