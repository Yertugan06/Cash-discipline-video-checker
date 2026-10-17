import hashlib
import re
from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.vision_types import Box, Detection, Point, Scene, center, distance, overlap


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
    for label in ("desk", "safe", "door", "laptop", "counter"):
        matches = [d for d in candidates if d.label == label]
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
    scene = Scene(objects=objects, zones=override.zones)
    for name, detection in objects.items():
        x1, y1, x2, y2 = detection.box
        scene.zones.setdefault(name, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
    if "desk" in objects and "laptop" in objects:
        origin = center(objects["desk"].box)
        anchor = center(objects["laptop"].box)
        length = distance(origin, anchor)
        if length > 0.025:
            scene.cashier_direction = tuple((anchor[i] - origin[i]) / length for i in (0, 1))
            scene.zones.setdefault("cashier", half_plane(origin, scene.cashier_direction, 1))
            scene.zones.setdefault("client", half_plane(origin, scene.cashier_direction, -1))
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


def in_zone(scene: Scene, name: str, point: Point, margin: float = 0) -> bool:
    import cv2

    polygon = scene.zones.get(name)
    if not polygon:
        return False
    return cv2.pointPolygonTest(np.asarray(polygon, dtype=np.float32), point, True) >= -margin
