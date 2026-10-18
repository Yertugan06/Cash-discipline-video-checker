"""Native-source crop geometry for offline object probes; not enabled in perception."""

from dataclasses import dataclass
from math import ceil, isfinite

from backend.f1.vision_types import Box, Detection


@dataclass(frozen=True)
class SourceCrop:
    """Integer pixel edges in the original image, before any model resizing."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom

    @property
    def size(self) -> tuple[int, int]:
        return self.right - self.left, self.bottom - self.top

    def validate(self, width: int, height: int) -> None:
        if not all(type(v) is int for v in (*self.bounds, width, height)):
            raise ValueError("Image sizes and crop edges must be integers")
        if not (0 <= self.left < self.right <= width and 0 <= self.top < self.bottom <= height):
            raise ValueError("Crop must have positive area inside the source image")

    def remap(self, box: Box, width: int, height: int) -> Box:
        """Map crop-normalised boxes, already unpadded by OWLv2, to the source."""
        self.validate(width, height)
        if len(box) != 4 or any(not isfinite(v) or not 0 <= v <= 1 for v in box):
            raise ValueError("Detection boxes must be finite and normalised to the crop")
        x1, y1, x2, y2 = box
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Detection boxes must have positive area")
        crop_width, crop_height = self.size
        return (
            (self.left + x1 * crop_width) / width,
            (self.top + y1 * crop_height) / height,
            (self.left + x2 * crop_width) / width,
            (self.top + y2 * crop_height) / height,
        )


def native_tiles(
    width: int, height: int, *, tile_size: int = 640, overlap: float = 0.25
) -> list[SourceCrop]:
    """Cover the entire source at a fixed pixel scale, independent of labels or objects.

    Tiles are cropped from the original image. The final tile reaches each image edge;
    evenly spaced starts avoid an almost identical extra edge tile. Small images yield
    a single crop. No upscaling or image decoding takes place here.
    """
    if any(type(v) is not int or v <= 0 for v in (width, height, tile_size)):
        raise ValueError("Image and tile sizes must be positive integers")
    if not isfinite(overlap) or not 0 <= overlap < 1:
        raise ValueError("Tile overlap must be finite and in [0, 1)")

    def starts(length: int) -> list[int]:
        extent = min(length, tile_size)
        count = ceil((length - extent) / max(1, int(tile_size * (1 - overlap))))
        return [round(i * (length - extent) / count) for i in range(count + 1)] if count else [0]

    crop_width, crop_height = min(width, tile_size), min(height, tile_size)
    return [
        SourceCrop(x, y, x + crop_width, y + crop_height)
        for y in starts(height)
        for x in starts(width)
    ]


def remap_detections(
    detections: list[Detection], crop: SourceCrop, width: int, height: int
) -> list[Detection]:
    """Return copies so detections reused by different variants cannot be mutated."""
    return [
        item.model_copy(update={"box": crop.remap(item.box, width, height)}, deep=True)
        for item in detections
    ]
