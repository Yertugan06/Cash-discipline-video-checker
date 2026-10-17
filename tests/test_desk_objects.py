import numpy as np
import pytest

pytest.importorskip("cv2", reason="backend.f1.desk_objects needs opencv-python (cv2)")

from backend.config import ROOT  # noqa: E402
from backend.f1.codex import load_codex  # noqa: E402
from backend.f1.desk_objects import (  # noqa: E402
    DeskObject,
    build_desk_objects,
    identity,
    origin_of,
)
from backend.f1.events import EventLog  # noqa: E402
from backend.f1.rules import Context, evaluate_rules  # noqa: E402
from backend.f1.vision_types import Detection, Event, Observation, Scene  # noqa: E402

H, W = 200, 300
DESK = (0.2, 0.3, 0.8, 0.8)
ITEM = (0.45, 0.5, 0.55, 0.6)
SAFE = (0.85, 0.1, 0.98, 0.4)


def rect(box):
    return [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]


def scene(**zones):
    return Scene(
        objects={"desk": Detection(label="desk", score=1, box=DESK)},
        zones={"desk": rect(DESK), **zones},
        confidence=1,
    )


def paint(image, box, value):
    x1, y1, x2, y2 = int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)
    image[y1:y2, x1:x2] = value


def frames(count, item_in, person_in=()):
    images, observations = [], []
    person = Detection(label="person", score=1, box=(0.4, 0.45, 0.6, 0.65), track_id="person:1")
    for index in range(count):
        image = np.full((H, W, 3), 120, dtype=np.uint8)
        if index in item_in:
            paint(image, ITEM, 40)
        detections = []
        if index in person_in:
            paint(image, person.box, 200)
            detections.append(person)
        images.append(image)
        observations.append(Observation(timestamp_sec=index * 0.5, detections=detections))
    return images, observations


def empty_log():
    return EventLog([], {}, [], {})


def test_an_item_put_on_the_desk_is_found_with_when_it_lay_there():
    images, observations = frames(12, item_in=range(4, 12))
    objects = build_desk_objects(images, observations, scene(), empty_log())
    assert len(objects) == 1
    assert objects[0].seen[0] == 2.0 and objects[0].seen[-1] == 5.5
    assert objects[0].box == pytest.approx(ITEM, abs=0.02)


def test_a_person_over_the_item_does_not_end_it():
    images, observations = frames(16, item_in=range(4, 16), person_in=range(8, 12))
    objects = build_desk_objects(images, observations, scene(), empty_log())
    assert len(objects) == 1
    assert objects[0].seen[0] == 2.0 and objects[0].seen[-1] == 7.5


def test_an_item_there_from_the_start_is_found_against_the_emptiest_moment():
    images, observations = frames(12, item_in=range(0, 6))
    objects = build_desk_objects(images, observations, scene(), empty_log())
    assert len(objects) == 1
    assert objects[0].seen[0] == 0.0 and objects[0].seen[-1] == 2.5
    assert objects[0].origin == "unknown"


def test_no_desk_means_no_desk_objects():
    images, observations = frames(4, item_in=())
    no_desk = Scene(objects={}, confidence=0)
    assert build_desk_objects(images, observations, no_desk, empty_log()) is None


def hand_at(timestamp, hand, box=(0.6, 0.2, 0.8, 0.7)):
    person = Detection(label="person", score=1, box=box, track_id="person:1", hands=[(*hand, 0.9)])
    return Observation(timestamp_sec=timestamp, detections=[person])


def test_the_origin_is_the_safe_when_the_placing_hand_came_from_it():
    obj = DeskObject(index=1, box=ITEM, seen=[5.0, 5.5, 6.0])
    observations = [hand_at(0, (0.1, 0.1)), hand_at(3.0, (0.9, 0.2)), hand_at(4.5, (0.5, 0.55))]
    assert origin_of(obj, observations, scene(safe=rect(SAFE))) == "safe"


def test_the_origin_is_the_client_side_when_the_placer_stands_there():
    client = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)]
    obj = DeskObject(index=1, box=ITEM, seen=[5.0, 5.5, 6.0])
    observations = [
        hand_at(0, (0.1, 0.1)),
        hand_at(4.5, (0.5, 0.55), box=(0.4, 0.0, 0.6, 0.4)),
    ]
    assert origin_of(obj, observations, scene(client=client)) == "client"


def test_no_hand_near_the_item_leaves_the_origin_unknown():
    obj = DeskObject(index=1, box=ITEM, seen=[5.0, 5.5, 6.0])
    observations = [hand_at(0, (0.1, 0.1)), hand_at(4.5, (0.05, 0.05))]
    assert origin_of(obj, observations, scene(safe=rect(SAFE))) == "unknown"


@pytest.mark.parametrize(
    ("origin", "counted", "detector", "kind"),
    [
        ("safe", False, "", ""),  # one clue is not enough
        ("unknown", False, "cash", ""),  # the detector alone is not enough
        ("safe", True, "", "cash"),
        ("counter", False, "cash", "cash"),
        ("client", False, "document", "document"),
        ("cashier", True, "cash", "cash"),
        ("safe", False, "bag", "bag"),
        ("cashier", False, "document", ""),
    ],
)
def test_an_item_kind_needs_two_clues_that_agree(origin, counted, detector, kind):
    obj = DeskObject(
        index=1, box=ITEM, seen=[1.0], origin=origin, counted=counted, detector_kind=detector
    )
    assert identity(obj)[0] == kind


def leave_context(desk_objects):
    leave = Event(type="EXIT", timestamp_sec=5, facts={"actor_id": "person:1", "role": "cashier"})
    log = EventLog([leave], {"roles": True, "desk": True}, [], {})
    return Context(
        load_codex(ROOT / "config" / "f1_codex.yaml"),
        log,
        [Observation(timestamp_sec=5, detections=[])],
        scene(),
        20,
        desk_objects,
    )


def desk_item(kind, seen, clues=("origin:safe", "counted")):
    return DeskObject(index=1, box=ITEM, seen=seen, kind=kind, clues=list(clues))


def leave_findings(desk_objects):
    findings = evaluate_rules(leave_context(desk_objects))
    return [f for f in findings if f.rule_id.startswith("L-NO-")]


def test_a_named_desk_item_still_there_after_the_leave_is_left_behind():
    findings = leave_findings([desk_item("cash", [3.0, 4.0, 6.0, 8.0, 10.0])])
    assert [f.rule_id for f in findings] == ["L-NO-CASH-ON-LEAVE"]
    assert findings[0].facts["track_ids"] == ["cash:desk1"]
    assert findings[0].facts["clues"] == ["counted", "origin:safe"]
    assert findings[0].facts["box"] == list(ITEM)


def test_a_desk_item_without_agreeing_clues_is_not_reported():
    assert leave_findings([desk_item("", [3.0, 4.0, 6.0, 8.0, 10.0], clues=["origin:safe"])]) == []


def test_a_desk_item_taken_along_is_not_left_behind():
    assert leave_findings([desk_item("cash", [3.0, 4.0, 5.0, 6.0])]) == []
