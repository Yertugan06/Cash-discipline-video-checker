"""A door-reaching departure must remain distinct from loss at work or clip cutoff."""

import pytest

from backend.config import ROOT
from backend.f1.events import EventBuilder, PersonHistory
from backend.f1.perception import load_perception_config
from backend.f1.vision_types import Detection, Observation, Scene, distance


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("hand_at_door", "EXIT"),
        ("hips_at_door", "EXIT"),
        ("stationary_seated", "TRACK_LOST"),
        ("working_at_safe", "TRACK_LOST"),
        ("uncertain_hand", "TRACK_LOST"),
        ("moving_away_from_door", "TRACK_LOST"),
        ("new_overlapping_track", "TRACK_LOST"),
        ("recording_cutoff", None),
    ],
)
def test_cashier_departure_requires_door_evidence_and_motion_before_observation_gap(case, expected):
    scene = Scene(
        objects={
            "desk": Detection(label="desk", score=1, box=(0.2, 0.5, 0.8, 0.8)),
            "door": Detection(label="door", score=1, box=(0.05, 0.05, 0.25, 0.4)),
            "safe": Detection(label="safe", score=1, box=(0.55, 0.2, 0.75, 0.45)),
        },
        confidence=1,
        zones={"door": [(0.05, 0.05), (0.25, 0.05), (0.25, 0.4), (0.05, 0.4)]},
    )
    origin, point, hands = (0.65, 0.65), (0.45, 0.4), [(0.2, 0.3, 0.9)]
    closest_desk = 0.0
    if case == "hips_at_door":
        point, hands = (0.15, 0.3), []
    elif case == "stationary_seated":
        origin, closest_desk = point, 0.1
    elif case == "working_at_safe":
        point, hands = (0.6, 0.4), [(0.62, 0.3, 0.9)]
    elif case == "uncertain_hand":
        hands = [(0.2, 0.3, 0.1)]
    elif case == "moving_away_from_door":
        origin = (0.35, 0.35)
    x, y = point
    cashier = Detection(
        label="person",
        score=0.9,
        track_id="cashier",
        role="cashier",
        box=(x - 0.1, y - 0.1, x + 0.1, y + 0.1),
        hands=hands,
    )
    builder = EventBuilder(scene, load_perception_config(ROOT / "config/perception.yaml"), 2)
    builder.cashier = "cashier"
    builder.people["cashier"] = PersonHistory(
        first=0,
        last=2,
        detection=cashier,
        origin=origin,
        role="cashier",
        announced=True,
        moved=distance(origin, point),
        closest_desk=closest_desk,
    )
    visible = []
    if case == "new_overlapping_track":
        continuation = cashier.model_copy(update={"track_id": "new-person", "role": "visitor"})
        builder.people["new-person"] = PersonHistory(
            first=2.5,
            last=3,
            detection=continuation,
            origin=point,
        )
        visible.append(continuation)
    timestamp = 2.5 if case == "recording_cutoff" else 3.5
    builder.push(Observation(timestamp_sec=timestamp, detections=visible))
    log = builder.finish(timestamp + 0.5)
    departures = [e for e in log.events if e.type in {"EXIT", "TRACK_LOST"}]
    assert [e.type for e in departures] == ([expected] if expected else [])
    if departures:
        assert departures[0].timestamp_sec == 2.5
        assert departures[0].facts["role"] == "cashier"
