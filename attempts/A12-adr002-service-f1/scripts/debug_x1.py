import json, glob, sys
sys.path.insert(0, "/app")
from backend.config import Settings
from backend.f1.vision_types import Scene, Observation
from backend.f1.events import build_events
from backend.f1.rules import Context, evaluate_rules
from backend.f1.codex import load_codex
from backend.f1.perception import load_perception_config

settings = Settings.from_env()
caches = sorted(glob.glob(str(settings.cache_dir / "*" / "*.json")))
print("cache files:", len(caches))
payload = json.load(open(caches[-1]))
scene = Scene.model_validate(payload["scene"])
obs = [Observation.model_validate(o) for o in payload["observations"]]
print("scene objects:", {k: (round(v.score, 3), [round(x, 3) for x in v.box]) for k, v in scene.objects.items()})
print("scene warnings:", scene.warnings)
print("frames:", len(obs), "last t:", obs[-1].timestamp_sec)

print("\n-- every coat/handbag detection (t, track, score, box) --")
for o in obs:
    for d in o.detections:
        if d.label in ("coat", "handbag"):
            print(f"t={o.timestamp_sec:5.1f} {d.track_id:12s} score={d.score:.3f} box={[round(x,3) for x in d.box]}")

print("\n-- people at 19..26 s --")
for o in obs:
    if 19 <= o.timestamp_sec <= 26:
        ppl = [(d.track_id, round(d.score, 2), [round(x, 2) for x in d.box]) for d in o.detections if d.label == "person"]
        print(f"t={o.timestamp_sec:5.1f}", ppl)

config = load_perception_config(settings.perception_config)
duration = obs[-1].timestamp_sec + 0.5
log = build_events(scene, obs, config, 2.0, duration)
print("\n-- PERSONAL_ON_DESK events --")
for e in log.events:
    if e.type.startswith("PERSONAL_ON_DESK"):
        print(e.type, e.timestamp_sec, {k: v for k, v in e.facts.items()})
ctx = Context(load_codex(settings.f1_codex_path), log, obs, scene, duration)
print("\n-- all legacy F1 findings (before knowledge-pack filter) --")
for f in evaluate_rules(ctx):
    print(f.rule_id, f.timestamp_sec, round(f.confidence, 3), f.facts)
