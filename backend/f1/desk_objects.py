"""Desk objects found by what changed on the desk, not by naming them (attempt A18).

An object is something that appears on the desk and stays there. What it is comes from clues
about its history: where the hand that put it down came from, whether the money counter ran
while it lay there, and what the open-vocabulary detector thought it looked like. A label
needs two clues to agree, so one wrong detector box can no longer decide a finding alone.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.f1.calibration import in_zone
from backend.f1.events import EventLog
from backend.f1.vision_types import Box, Observation, Scene, center, contains, distance, overlap

WORK_WIDTH = 320  # desk crop width in pixels for the change maps
DIFF_THRESHOLD = 35  # per-channel absolute difference (0-255) that counts as changed
MIN_AREA = 0.002  # blob area as a fraction of the desk crop
MAX_AREA = 0.25
MAX_CHANGED = 0.4  # more of the visible desk changed than this: lighting or camera, not objects
MAX_OCCLUDED = 0.1  # a background candidate has at most this much of the desk under a person
LINK_IOU = 0.3
GAP_FRAMES = 2  # visible frames an object may be missing before it counts as gone
MIN_FRAMES = 3  # 1.5 s at the F1 sampling rate
HAND_REACH = 0.15  # normalised distance from a wrist to an object it just put down
ORIGIN_LOOKBACK_SEC = 3.0
COUNT_LOOKBACK_SEC = 10.0
DETECTOR_MIN_FRAMES = 2

# Detector labels that are a clue for a rule's item kind; "tablet" is left out because the
# prompt matches the laptop itself (A17).
DETECTOR_KINDS = {
    "cash": "cash",
    "bundle": "cash",
    "bag": "bag",
    "document": "document",
    "id_card": "document",
}
# Which item kinds a starting place makes plausible. Cash and cash bags are kept in the safe and
# come out of the money counter; whatever crosses from the client side may be cash, documents
# or a collector's bag. Things the cashier brings from their own side are no clue.
ORIGIN_KINDS = {
    "safe": {"cash", "bag"},
    "counter": {"cash"},
    "client": {"cash", "document", "bag"},
}
KIND_PREFERENCE = ("cash", "bag", "document")


@dataclass
class DeskObject:
    index: int
    box: Box  # normalised, median of the boxes it was seen in
    seen: list[float]  # timestamps of the frames it was seen in
    origin: str = "unknown"
    counted: bool = False
    detector_kind: str = ""
    kind: str = ""
    clues: list[str] = field(default_factory=list)

    @property
    def track_id(self) -> str:
        return f"{self.kind or 'item'}:desk{self.index}"

    def present(self, timestamp: float, tolerance: float = 0.5) -> bool:
        return self.seen[0] - tolerance <= timestamp <= self.seen[-1] + tolerance


Rect = tuple[int, int, int, int]


def crop_size(image_shape: tuple[int, ...], desk: Box) -> tuple[int, int]:
    width = max((desk[2] - desk[0]) * image_shape[1], 1)
    height = max((desk[3] - desk[1]) * image_shape[0], 1)
    return WORK_WIDTH, max(int(round(WORK_WIDTH * height / width)), 1)


def desk_crop(image: np.ndarray, desk: Box) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1 = int(desk[0] * w), int(desk[1] * h)
    x2, y2 = max(int(desk[2] * w), x1 + 1), max(int(desk[3] * h), y1 + 1)
    return cv2.resize(image[y1:y2, x1:x2], crop_size(image.shape, desk))


def to_crop(box: Box, desk: Box, size: tuple[int, int]) -> Rect:
    width, height = size
    sx, sy = width / (desk[2] - desk[0]), height / (desk[3] - desk[1])
    x1 = int(np.clip((box[0] - desk[0]) * sx, 0, width))
    y1 = int(np.clip((box[1] - desk[1]) * sy, 0, height))
    x2 = int(np.clip(np.ceil((box[2] - desk[0]) * sx), 0, width))
    y2 = int(np.clip(np.ceil((box[3] - desk[1]) * sy), 0, height))
    return x1, y1, x2, y2


def from_crop(rect: Rect, desk: Box, size: tuple[int, int]) -> Box:
    width, height = size
    sx, sy = (desk[2] - desk[0]) / width, (desk[3] - desk[1]) / height
    return (
        desk[0] + rect[0] * sx,
        desk[1] + rect[1] * sy,
        desk[0] + rect[2] * sx,
        desk[1] + rect[3] * sy,
    )


def box_mask(boxes: Iterable[Box], desk: Box, size: tuple[int, int]) -> np.ndarray:
    mask = np.zeros((size[1], size[0]), dtype=bool)
    for box in boxes:
        x1, y1, x2, y2 = to_crop(box, desk, size)
        mask[y1:y2, x1:x2] = True
    return mask


def rect_iou(a: Rect, b: Rect) -> float:
    return overlap(tuple(map(float, a)), tuple(map(float, b)))


def edge_energy(crop: np.ndarray, invalid: np.ndarray) -> float:
    gray = cv2.GaussianBlur(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    valid = ~invalid
    return float(edges[valid].mean()) if valid.any() else float("inf")


def desk_background(crops: list[np.ndarray], occluded: list[np.ndarray], fixed: np.ndarray) -> int:
    """Index of the emptiest moment in the clip: among frames with (almost) no one over the desk,
    the one with the least edge energy, since every object on a desk adds edges."""
    fractions = [mask.mean() for mask in occluded]
    candidates = [i for i, value in enumerate(fractions) if value <= MAX_OCCLUDED]
    if not candidates:
        order = sorted(range(len(crops)), key=lambda i: fractions[i])
        candidates = order[: max(1, len(order) // 10)]
    return min(candidates, key=lambda i: edge_energy(crops[i], occluded[i] | fixed))


def desk_blobs(crop: np.ndarray, background: np.ndarray, invalid: np.ndarray) -> list[Rect] | None:
    """Changed regions against the background, or None when the frame says nothing (the desk is
    hidden, or most of it changed at once, which is lighting or the camera)."""
    valid = ~invalid
    if valid.mean() < 0.2:
        return None
    frame = crop.astype(np.float32)
    reference = background.astype(np.float32)
    # Cameras re-expose as people move; match the frame's brightness to the background first.
    gain = reference[valid].mean(axis=0) / np.maximum(frame[valid].mean(axis=0), 1)
    frame = np.clip(frame * gain, 0, 255)
    diff = np.abs(cv2.GaussianBlur(frame, (5, 5), 0) - cv2.GaussianBlur(reference, (5, 5), 0))
    changed = (diff.max(axis=2) > DIFF_THRESHOLD) & valid
    if changed.sum() > MAX_CHANGED * valid.sum():
        return None
    changed = changed.astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    changed = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(changed)
    total = changed.size
    return [
        (int(x), int(y), int(x + w), int(y + h))
        for x, y, w, h, area in stats[1:count]
        if MIN_AREA <= area / total <= MAX_AREA
    ]


def link_objects(
    timestamps: list[float],
    blobs: list[list[Rect] | None],
    invalid: list[np.ndarray],
) -> list[tuple[list[float], list[Rect]]]:
    """Join blobs across frames by overlap. A frame where the object's place is hidden is no
    evidence either way; it is gone after GAP_FRAMES visible frames without it."""
    active: list[dict] = []
    done: list[dict] = []
    for timestamp, frame_blobs, hidden in zip(timestamps, blobs, invalid, strict=True):
        if frame_blobs is None:
            continue
        free = list(frame_blobs)
        for track in active:
            best = max(free, key=lambda rect: rect_iou(rect, track["rects"][-1]), default=None)
            if best is not None and rect_iou(best, track["rects"][-1]) >= LINK_IOU:
                free.remove(best)
                track["seen"].append(timestamp)
                track["rects"].append(best)
                track["misses"] = 0
                continue
            x1, y1, x2, y2 = track["rects"][-1]
            place = hidden[y1:y2, x1:x2]
            if place.size and place.mean() <= 0.5:
                track["misses"] += 1
        done += [track for track in active if track["misses"] > GAP_FRAMES]
        active = [track for track in active if track["misses"] <= GAP_FRAMES]
        active += [{"seen": [timestamp], "rects": [rect], "misses": 0} for rect in free]
    return [
        (track["seen"], track["rects"])
        for track in done + active
        if len(track["seen"]) >= MIN_FRAMES
    ]


def origin_of(obj: DeskObject, observations: list[Observation], scene: Scene) -> str:
    """Where the hand that put the object down came from in the seconds before it appeared."""
    if not observations or obj.seen[0] <= observations[0].timestamp_sec + 0.5:
        return "unknown"  # already on the desk when the clip starts
    start = obj.seen[0] - ORIGIN_LOOKBACK_SEC
    window = [o for o in observations if start <= o.timestamp_sec <= obj.seen[0]]
    spot = center(obj.box)
    placer = None
    for observation in reversed(window):
        reach = [
            (distance(hand, spot), person.track_id)
            for person in observation.detections
            if person.label == "person"
            for hand in person.wrists()
        ]
        reach = [item for item in reach if item[0] <= HAND_REACH]
        if reach:
            placer = min(reach)[1]
            break
    if placer is None:
        return "unknown"
    path = [
        person
        for observation in window
        for person in observation.detections
        if person.label == "person" and person.track_id == placer
    ]
    hands = [hand for person in path for hand in person.wrists()]
    for name in ("safe", "counter"):
        if any(in_zone(scene, name, hand, 0.02) for hand in hands):
            return name
    if "client" in scene.zones and any(in_zone(scene, "client", p.position()) for p in path):
        return "client"
    return "cashier"


def was_counted(obj: DeskObject, log: EventLog) -> bool:
    return any(
        event.type == "COUNT_START"
        and obj.seen[0] - COUNT_LOOKBACK_SEC <= event.timestamp_sec <= obj.seen[-1]
        for event in log.events
    )


def detector_kind(obj: DeskObject, observations: list[Observation]) -> str:
    seen = set(obj.seen)
    frames: Counter[str] = Counter()
    for observation in observations:
        if observation.timestamp_sec not in seen:
            continue
        kinds = {
            DETECTOR_KINDS[d.label]
            for d in observation.detections
            if d.label in DETECTOR_KINDS
            and (overlap(d.box, obj.box) > 0.2 or contains(obj.box, center(d.box)))
        }
        frames.update(kinds)
    best = max(frames.items(), key=lambda item: item[1], default=None)
    return best[0] if best and best[1] >= DETECTOR_MIN_FRAMES else ""


def identity(obj: DeskObject) -> tuple[str, list[str]]:
    """The item kind at least two clues agree on, and the clues behind it."""
    votes: Counter[str] = Counter()
    clues = []
    if obj.origin in ORIGIN_KINDS:
        votes.update(ORIGIN_KINDS[obj.origin])
        clues.append(f"origin:{obj.origin}")
    if obj.counted:
        votes["cash"] += 1
        clues.append("counted")
    if obj.detector_kind:
        votes[obj.detector_kind] += 1
        clues.append(f"detector:{obj.detector_kind}")
    agreed = [kind for kind in KIND_PREFERENCE if votes[kind] >= 2]
    if not agreed:
        return "", clues
    kind = max(agreed, key=lambda k: (votes[k], -KIND_PREFERENCE.index(k)))
    return kind, clues


def build_desk_objects(
    images: Iterable[np.ndarray],
    observations: list[Observation],
    scene: Scene,
    log: EventLog,
) -> list[DeskObject] | None:
    """Desk objects for one clip; `images` are the BGR frames `observations` were made from.
    None when the desk was never localised."""
    if "desk" not in scene.objects:
        return None
    desk = scene.objects["desk"].box
    crops, occluded = [], []
    for image, observation in zip(images, observations, strict=False):
        crop = desk_crop(image, desk)
        size = (crop.shape[1], crop.shape[0])
        people = [d.box for d in observation.detections if d.label == "person"]
        crops.append(crop)
        occluded.append(box_mask(people, desk, size))
    if not crops:
        return None
    size = (crops[0].shape[1], crops[0].shape[0])
    # The laptop and the money counter stand on the desk; they are fixtures, not items.
    fixed = box_mask(
        [scene.objects[n].box for n in ("laptop", "counter") if n in scene.objects], desk, size
    )
    reference = desk_background(crops, occluded, fixed)
    background, hidden_then = crops[reference], occluded[reference]
    invalid = [mask | fixed | hidden_then for mask in occluded]
    timestamps = [o.timestamp_sec for o in observations[: len(crops)]]
    blobs = [desk_blobs(c, background, m) for c, m in zip(crops, invalid, strict=True)]
    objects = []
    for index, (seen, rects) in enumerate(link_objects(timestamps, blobs, invalid), start=1):
        median = tuple(int(v) for v in np.median(np.array(rects), axis=0))
        obj = DeskObject(index=index, box=from_crop(median, desk, size), seen=seen)
        obj.origin = origin_of(obj, observations, scene)
        obj.counted = was_counted(obj, log)
        obj.detector_kind = detector_kind(obj, observations)
        obj.kind, obj.clues = identity(obj)
        objects.append(obj)
    return objects
