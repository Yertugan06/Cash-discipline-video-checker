"""Camera-independent observations. Coordinates are normalised to the image extent."""

from math import hypot

from pydantic import BaseModel, ConfigDict, Field


class Event(BaseModel):
    """An F1-internal visible event (not part of the frozen contracts)."""

    model_config = ConfigDict(allow_inf_nan=False)
    timestamp_sec: float = Field(ge=0)
    type: str
    facts: dict[str, str | int | float | bool | list[float] | list[str]] = Field(
        default_factory=dict
    )


Box = tuple[float, float, float, float]
Point = tuple[float, float]


def center(box: Box) -> Point:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def desk_scale(box: Box) -> float:
    """The desk's long side relative to the original 70%-of-image reference."""
    x1, y1, x2, y2 = box
    return max(x2 - x1, y2 - y1) / 0.70


def contains(box: Box, point: Point, margin: float = 0) -> bool:
    return box[0] - margin <= point[0] <= box[2] + margin and (
        box[1] - margin <= point[1] <= box[3] + margin
    )


def overlap(a: Box, b: Box) -> float:
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    return intersection / max(
        (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection,
        1e-8,
    )


class Detection(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    label: str
    score: float = Field(ge=0, le=1)
    box: Box
    track_id: str = ""
    role: str = "unknown"
    body: list[tuple[float, float, float]] = Field(default_factory=list)
    hands: list[tuple[float, float, float]] = Field(default_factory=list)

    def wrists(self, threshold: float = 0.3) -> list[Point]:
        hands = [
            (x, y)
            for x, y, score in self.hands
            if score >= threshold and 0 <= x <= 1 and 0 <= y <= 1
        ]
        if not hands:
            hands = [
                (x, y)
                for x, y, score in self.body[9:11]
                if score >= threshold and 0 <= x <= 1 and 0 <= y <= 1
            ]
        return hands

    def position(self) -> Point:
        hips = [
            (x, y)
            for x, y, score in self.body[11:13]
            if score >= 0.3 and 0 <= x <= 1 and 0 <= y <= 1
        ]
        if hips:
            return tuple(sum(point[i] for point in hips) / len(hips) for i in (0, 1))
        return center(self.box)


def worn_or_carried(item: Detection, people: list[Detection], hand_distance: float) -> bool:
    x1, y1, x2, y2 = item.box
    area = max((x2 - x1) * (y2 - y1), 1e-8)
    for person in people:
        p1, q1, p2, q2 = person.box
        intersection = max(0, min(x2, p2) - max(x1, p1)) * max(0, min(y2, q2) - max(y1, q1))
        if item.label == "coat" and intersection / area > 0.7:
            if area > 0.35 * (p2 - p1) * (q2 - q1):
                return True
            torso = person.body[5:7] + person.body[11:13]
            if len(torso) == 4 and all(
                score >= 0.3 and 0 <= x <= 1 and 0 <= y <= 1 for x, y, score in torso
            ):
                shoulders = tuple((torso[0][i] + torso[1][i]) / 2 for i in (0, 1))
                hips = tuple((torso[2][i] + torso[3][i]) / 2 for i in (0, 1))
                direction = tuple(hips[i] - shoulders[i] for i in (0, 1))
                # A worn coat can be detected as only a shoulder/collar fragment. A
                # desk coat overlapping the person below the hips is still eligible.
                if any(direction) and all(
                    (x - hips[0]) * direction[0] + (y - hips[1]) * direction[1] < 0
                    for x in (x1, x2)
                    for y in (y1, y2)
                ):
                    return True
        if item.label == "handbag" and any(
            distance(hand, center(item.box)) < hand_distance for hand in person.wrists()
        ):
            return True
    return False


class State(BaseModel):
    value: str
    score: float = Field(ge=0, le=1)
    margin: float = Field(ge=0, le=1)


class Observation(BaseModel):
    timestamp_sec: float = Field(ge=0)
    detections: list[Detection]
    states: dict[str, State] = Field(default_factory=dict)


class Scene(BaseModel):
    objects: dict[str, Detection]
    zones: dict[str, list[Point]] = Field(default_factory=dict)
    cashier_direction: Point | None = None
    cashier_position: Point | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    candidates: list[Detection] = Field(default_factory=list)  # raw calibration detections

    def scaled_distance(self, value: float) -> float:
        """Distances were specified for a desk spanning about 70% of the image.

        Use its long side for either desk orientation; without a calibrated desk the
        scale is unknown, so retain the original distance.
        """
        desk = self.objects.get("desk")
        if desk is None:
            return value
        return value * desk_scale(desk.box)

    def cashier_side(self, point: Point) -> bool:
        if not self.cashier_direction or "desk" not in self.objects:
            return False
        origin = center(self.objects["desk"].box)
        return sum((point[i] - origin[i]) * self.cashier_direction[i] for i in (0, 1)) >= 0
