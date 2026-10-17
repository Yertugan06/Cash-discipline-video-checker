import hashlib
import re
from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.f1.vision_types import (
    Box,
    Detection,
    Observation,
    Point,
    Scene,
    center,
    contains,
    distance,
    overlap,
)

LAPTOP_REACH = 0.25  # normalised distance from the laptop centre to someone working at it
LAPTOP_HAND_MARGIN = 0.08
MIN_ALONE_FRAMES = 3  # 1.5 s at the F1 sampling rate


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objects: dict[str, Box] = Field(default_factory=dict)
    zones: dict[str, list[Point]] = Field(default_factory=dict)

    @field_validator("objects", "zones")
    @classmethod
    def normalised(cls, value):
        for coords in value.values():
            values = [v for pair in coords for v in pair] if isinstance(coords, list) else coords
            if any(not np.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError("Override coordinates must be finite and in [0, 1]")
        return value

    @field_validator("objects")
    @classmethod
    def positive_boxes(cls, value):
        for x1, y1, x2, y2 in value.values():
            if x1 >= x2 or y1 >= y2:
                raise ValueError("Override boxes must have positive area")
        return value

    @field_validator("zones")
    @classmethod
    def polygons(cls, value):
        if any(len(polygon) < 3 for polygon in value.values()):
            raise ValueError("Zone polygons need at least three vertices")
        return value


def video_checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def half_plane(origin: Point, direction: Point, sign: int) -> list[Point]:
    polygon = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    def side(point):
        return sign * sum((point[i] - origin[i]) * direction[i] for i in (0, 1))

    output = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        a, b = side(start), side(end)
        if a >= 0:
            output.append(start)
        if (a >= 0) != (b >= 0):
            ratio = a / (a - b)
            output.append(tuple(start[i] + ratio * (end[i] - start[i]) for i in (0, 1)))
    return output


def calibrate(candidates: list[Detection], overrides_path: Path, checksum: str) -> Scene:
    objects = {}
    # Laptop first: the cash desk is the desk the laptop stands on. Without this the desk
    # prompt often matches an office desk seen through the glass wall, which flips the
    # cashier/client half-planes over the whole frame.
    for label in ("laptop", "desk", "safe", "door", "counter"):
        matches = [d for d in candidates if d.label == label]
        if label == "desk":
            laptop = objects.get("laptop")
            matches = [d for d in matches if laptop and contains(d.box, center(laptop.box), 0.02)]
        if not matches:
            continue
        best = max(
            matches, key=lambda d: sum(x.score for x in matches if overlap(d.box, x.box) > 0.3)
        )
        cluster = [d for d in matches if overlap(best.box, d.box) > 0.3]
        box = tuple(float(v) for v in np.median([d.box for d in cluster], axis=0))
        objects[label] = Detection(
            label=label, score=float(np.mean([d.score for d in cluster])), box=box
        )
    data = yaml.safe_load(overrides_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {"videos"}:
        raise ValueError("Override file must contain a videos mapping")
    entries = data.get("videos", {})
    if not isinstance(entries, dict):
        raise ValueError("Override videos must be a mapping keyed by SHA-256")
    if any(not re.fullmatch(r"[0-9a-fA-F]{64}", str(key)) for key in entries):
        raise ValueError("Override keys must be complete SHA-256 hashes, not clip names")
    entries = {key.lower(): value for key, value in entries.items()}
    override = Override.model_validate(entries.get(checksum, {}))
    for label, box in override.objects.items():
        if label not in {"desk", "safe", "door", "laptop", "counter"}:
            raise ValueError(f"Unknown static object override: {label}")
        objects[label] = Detection(label=label, score=1, box=box)
    scene = Scene(objects=objects, zones=override.zones, candidates=candidates)
    for name, detection in objects.items():
        x1, y1, x2, y2 = detection.box
        scene.zones.setdefault(name, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
    if "desk" in objects and "laptop" in objects:
        # The cashier/client split needs to know where the cashier works; see orient_cashier_side.
        scene.confidence = min(objects["desk"].score * 3, objects["laptop"].score * 3, 1)
    if "cashier" in override.zones and "client" in override.zones:
        scene.confidence = 1
    if scene.confidence < 0.3:
        scene.warnings.append(
            "Рабочая и клиентская зоны не откалиброваны уверенно; задайте ручные зоны."
        )
    missing = [
        name for name in ("desk", "laptop", "safe", "door", "counter") if name not in objects
    ]
    if missing:
        scene.warnings.append("Не локализованы объекты сцены: " + ", ".join(missing))
    return scene


def behind_glass(scene: Scene, box: Box, margin: float) -> bool:
    """Anyone in the room stands in front of, at or behind the desk (hidden by it); a person box
    ending above the desk's far edge is a reflection in the glass wall or someone behind it."""
    desk = scene.objects.get("desk")
    return desk is not None and box[3] < desk.box[1] - margin


def orient_cashier_side(scene: Scene, observations: list[Observation], glass_margin: float) -> None:
    """Split the room along the desk's long side, cashier on the side where a person works at
    the laptop while alone in the room. Clients and collectors only come in while the cashier
    is there, so a lone person at the workstation is the cashier, whatever the camera angle
    (over the shoulder, facing the cashier, from the side). Manual zones win."""
    if "cashier" in scene.zones or "desk" not in scene.objects or "laptop" not in scene.objects:
        return
    laptop = center(scene.objects["laptop"].box)
    alone = []
    reaching = []
    for observation in observations:
        people = [
            d
            for d in observation.detections
            if d.label == "person" and not behind_glass(scene, d.box, glass_margin)
        ]
        if len(people) == 1:
            person = people[0]
            if distance(person.position(), laptop) <= LAPTOP_REACH:
                alone.append(person.position())
            elif any(
                contains(scene.objects["laptop"].box, hand, LAPTOP_HAND_MARGIN)
                for hand in person.wrists()
            ):
                reaching.append(person.position())
    # Keep an established workstation anchor; use hands when hips alone cannot locate it.
    if len(alone) < MIN_ALONE_FRAMES:
        alone.extend(reaching)
    if len(alone) < MIN_ALONE_FRAMES:
        scene.confidence = 0
        scene.warnings.append(
            "Кассир ни разу не виден один за рабочим местом; сторону кассира не определить, "
            "задайте ручные зоны."
        )
        return
    anchor = tuple(float(np.median([p[i] for p in alone])) for i in (0, 1))
    scene.cashier_position = anchor
    x1, y1, x2, y2 = scene.objects["desk"].box
    origin = center(scene.objects["desk"].box)
    axis = 1 if x2 - x1 >= y2 - y1 else 0  # a desk wide in the image splits top/bottom
    side = 1.0 if anchor[axis] >= origin[axis] else -1.0
    scene.cashier_direction = (0.0, side) if axis else (side, 0.0)
    scene.zones["cashier"] = half_plane(origin, scene.cashier_direction, 1)
    scene.zones["client"] = half_plane(origin, scene.cashier_direction, -1)


def in_zone(scene: Scene, name: str, point: Point, margin: float = 0) -> bool:
    import cv2

    polygon = scene.zones.get(name)
    if not polygon:
        return False
    return cv2.pointPolygonTest(np.asarray(polygon, dtype=np.float32), point, True) >= -margin
