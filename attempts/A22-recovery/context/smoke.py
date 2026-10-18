"""One explicit numeric cache -> current event trace -> bounded context; no pixels/models."""

import hashlib
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path

from backend.f1.visual_checks import CheckRequest, VisualCheckSettings, cache_identity

from backend.config import ROOT
from backend.f1.detector import build_trace
from backend.f1.events import build_events
from backend.f1.llm_context import build_llm_context
from backend.f1.perception import load_perception_config
from backend.f1.vision_types import Observation, Scene

cache, target, output = Path(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
payload = json.loads(cache.read_text())
scene = Scene.model_validate(payload["scene"])
observations = [Observation.model_validate(row) for row in payload["observations"]]
config = load_perception_config(ROOT / "config/perception.yaml")
duration = observations[-1].timestamp_sec + 0.5
log = build_events(scene, observations, config, 2, duration)
trace = build_trace(cache.parent.name, config, duration, scene, observations, log)
started = time.perf_counter()
context = build_llm_context(scene, observations, log, target)
elapsed_ms = (time.perf_counter() - started) * 1000
encoded = json.dumps(context, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
assert len(encoded.encode()) <= 16000
assert context["target_t"] == target
request = CheckRequest("safe", target, None, "context-smoke", "numeric-only", target)
grounding = json.dumps(
    {
        "target_t": target,
        "window": {
            key: context["window"][key]
            for key in (
                "start",
                "end",
                "available_observation_extent",
                "target_sample_exists",
                "observation_gap_intervals",
            )
        },
        "scene_objects": context["scene"]["objects"],
        "actors": [{"track_id": a["track_id"], "sample": a["sample"]} for a in context["actors"]],
    },
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
)
with_context = replace(request, context_json=grounding)
assert "state_samples" not in grounding and "events" not in grounding
assert with_context.prompt != request.prompt
identity = {"backend": "smoke_no_model", "files_sha256": "not_inferred"}
old_key = cache_identity("0" * 64, identity, request, VisualCheckSettings(), 2, "1" * 64)
new_key = cache_identity("0" * 64, identity, with_context, VisualCheckSettings(), 2, "1" * 64)
assert old_key != new_key and new_key["prompt"] == with_context.prompt
assert new_key["request"] == asdict(with_context)
roles = defaultdict(set)
for observation in observations:
    for detection in observation.detections:
        if detection.label == "person":
            roles[detection.track_id].add(detection.role)
summary = {
    "cache_path": str(cache),
    "cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
    "source_root": str(ROOT),
    "observations": len(observations),
    "events": len(log.events),
    "target_t": target,
    "context_bytes": len(encoded.encode()),
    "context_build_ms": round(elapsed_ms, 3),
    "actual_grounding_bytes": len(grounding.encode()),
    "scene_confidence": context["scene"]["confidence"],
    "fixture_detection_scores": {
        key: value["score"] for key, value in context["scene"]["objects"].items()
    },
    "coverage_flags": log.coverage,
    "role_values_by_track": {key: sorted(value) for key, value in roles.items()},
    "omitted": context["omitted"],
    "actual_prompt_and_context_change_fingerprint": True,
    "model_inference_ran": False,
}
output.mkdir(parents=True, exist_ok=True)
for name, value in (
    ("real-context.json", context),
    ("real-trace.json", trace),
    ("smoke-result.json", summary),
):
    (output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
print(json.dumps(summary, sort_keys=True))
