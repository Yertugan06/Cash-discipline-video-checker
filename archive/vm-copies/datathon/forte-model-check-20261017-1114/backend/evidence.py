import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.codex import Codex
from backend.models import EvidenceFrame, Violation
from backend.rules import Finding
from backend.vision_types import Observation, Scene

COLORS = {"cashier": "#e34377", "client": "#30a4f4", "collector": "#edac32", "outsider": "#ff3b30"}


def annotate(
    image: Image.Image, observation: Observation, scene: Scene, *, tracks: set[str] | None = None
) -> Image.Image:
    image = image.copy().convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = ImageFont.load_default(size=max(11, round(width / 42)))
    if tracks is None:
        for name, polygon in scene.zones.items():
            vertices = [(x * width, y * height) for x, y in polygon]
            if vertices:
                draw.line(vertices + vertices[:1], fill=COLORS.get(name, "#9e9e9e"), width=2)
    for name, detection in scene.objects.items():
        if tracks is not None and name not in tracks and "desk" != name:
            continue
        x1, y1, x2, y2 = detection.box
        draw.rectangle(
            (x1 * width, y1 * height, x2 * width, y2 * height), outline="#ffc54f", width=2
        )
        state = observation.states.get(name)
        text = name + (":" + state.value if state else "")
        draw.text(
            (x1 * width, max(0, y1 * height - 15)),
            text,
            font=font,
            fill="#ffc54f",
            stroke_width=1,
            stroke_fill="black",
        )
    for detection in observation.detections:
        if tracks is not None and detection.track_id not in tracks:
            continue
        x1, y1, x2, y2 = detection.box
        color = COLORS.get(detection.role, "#54de7d")
        draw.rectangle((x1 * width, y1 * height, x2 * width, y2 * height), outline=color, width=2)
        name = detection.role if detection.label == "person" else detection.label
        text = f"{detection.track_id} {name} {detection.score:.2f}"
        draw.text(
            (x1 * width, y1 * height),
            text,
            font=font,
            fill=color,
            stroke_width=1,
            stroke_fill="black",
        )
        if detection.label == "person":
            for x, y, score in detection.hands:
                if score >= 0.3 and 0 <= x <= 1 and 0 <= y <= 1:
                    draw.ellipse(
                        (x * width - 2, y * height - 2, x * width + 2, y * height + 2), fill=color
                    )
    draw.text(
        (8, 8),
        f"{observation.timestamp_sec:.2f} s",
        font=font,
        fill="white",
        stroke_width=2,
        stroke_fill="black",
    )
    return image


def build_violations(
    findings: list[Finding],
    codex: Codex,
    frames: list[Path],
    observations: list[Observation],
    scene: Scene,
    fps: float,
    output_dir: Path,
) -> list[Violation]:
    rules = {rule.id: rule for rule in codex.rules}
    results = []
    for number, finding in enumerate(findings):
        rule = rules[finding.rule_id]
        related = set(finding.facts.get("track_ids", [])) | set(
            finding.facts.get("static_objects", [])
        )
        related.update(
            str(finding.facts[key])
            for key in ("actor_id", "track_id", "from_id", "to_id")
            if key in finding.facts
        )
        evidence = []
        indices = sorted(
            {
                min(len(frames) - 1, max(0, round((finding.timestamp_sec + offset) * fps)))
                for offset in (-1, 0, 1)
            }
        )
        folder = output_dir / "violations" / f"{number:03d}-{rule.id}"
        folder.mkdir(parents=True, exist_ok=True)
        for index in indices:
            with Image.open(frames[index]) as image:
                rendered = annotate(image, observations[index], scene, tracks=related or None)
            stream = io.BytesIO()
            rendered.save(stream, format="JPEG", quality=88)
            content = stream.getvalue()
            timestamp = index / fps
            (folder / f"{timestamp:.3f}.jpg").write_bytes(content)
            evidence.append(
                EvidenceFrame(
                    timestamp_sec=timestamp, image_base64=base64.b64encode(content).decode("ascii")
                )
            )
        description = rule.description_template.format(time=f"{finding.timestamp_sec:.1f}")
        description += f" Правило: {rule.id}. Источник: {rule.source}."
        description_en = rule.description_template_en.format(time=f"{finding.timestamp_sec:.1f}")
        description_en += f" Rule: {rule.id}. Source: {rule.source}."
        scores = [
            d.score for i in indices for d in observations[i].detections if d.track_id in related
        ]
        scores.extend(scene.objects[name].score for name in related if name in scene.objects)
        if not scores:
            scores = [d.score for d in scene.objects.values()]
        confidence = min([finding.confidence, *scores]) if scores else 0.0
        results.append(
            Violation(
                type=rule.title,
                timecode_sec=finding.timestamp_sec,
                description=description,
                evidence_frames=evidence,
                rule_id=rule.id,
                source=rule.source,
                source_url=rule.source_url,
                strength=rule.strength,
                confidence=max(0, min(confidence, 1)),
                type_en=rule.title_en,
                description_en=description_en,
            )
        )
    return results


def render_debug(
    frames: list[Path], observations: list[Observation], scene: Scene, destination: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for index, (frame, observation) in enumerate(zip(frames, observations, strict=True)):
        with Image.open(frame) as image:
            rendered = annotate(image, observation, scene)
            rendered.save(destination / f"{index + 1:06d}.jpg", quality=80)
