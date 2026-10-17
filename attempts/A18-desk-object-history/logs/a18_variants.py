"""Scratch: which half of A18 fails? Same clips, desk objects built once, leave rules re-run
with different ways of naming the desk objects."""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, "/work")
sys.path.insert(0, "/work/scripts")
from replay_f1 import desk_objects_for

from backend.config import ROOT
from backend.f1.calibration import calibrate, video_checksum
from backend.f1.codex import load_codex
from backend.f1.detector import FPS
from backend.f1.events import build_events
from backend.f1.perception import load_perception_config
from backend.f1.rules import Context, evaluate_rules
from backend.f1.vision_types import Observation, Scene

VARIANTS = {
    "a18": lambda o: o.kind,  # 2 clues agree (as committed)
    "any_item": lambda o: "cash",  # identity ignored: anything left counts
    "detector_only": lambda o: o.detector_kind,  # detector label, but only on desk-change objects
    "one_clue": lambda o: (
        o.kind
        or o.detector_kind
        or ("cash" if o.counted or o.origin in {"safe", "counter"} else "")
    ),
}
config = load_perception_config(ROOT / "config" / "perception.yaml")
codex = load_codex(ROOT / "config" / "f1_codex.yaml")
enabled = {
    r["rule_id"]
    for r in yaml.safe_load((ROOT / "knowledge" / "rules.yaml").read_text())
    if r.get("enabled")
}
videos = {video_checksum(p): p for p in Path("/videos").iterdir() if p.is_file()}
for video_dir in sorted(p for p in Path("/app/runtime/perception_cache").iterdir() if p.is_dir()):
    files = list(video_dir.glob("*.json"))
    if not files or video_dir.name not in videos:
        continue
    payload = json.loads(max(files, key=lambda p: p.stat().st_mtime).read_text())
    scene = Scene.model_validate(payload["scene"])
    if scene.candidates:
        scene = calibrate(scene.candidates, ROOT / "config" / "overrides.yaml", video_dir.name)
    observations = [Observation.model_validate(o) for o in payload["observations"]]
    duration = observations[-1].timestamp_sec + 1 / FPS
    log = build_events(scene, observations, config, FPS, duration)
    objects = desk_objects_for(videos[video_dir.name], observations, scene, log)
    out = {"sha256": video_dir.name}
    for name, kind_of in VARIANTS.items():
        if objects is not None:
            for o in objects:
                o.kind = kind_of(o)
        findings = evaluate_rules(Context(codex, log, observations, scene, duration, objects))
        out[name] = [
            {"rule_id": f.rule_id, "t": round(f.timestamp_sec, 1)}
            for f in findings
            if f.rule_id in enabled
        ]
    print(json.dumps(out), flush=True)
