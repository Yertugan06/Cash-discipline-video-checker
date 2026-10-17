"""Debug overlay: every tracked detection plus scene objects at one timestamp."""
import glob, json, sys
sys.path.insert(0, "/app")
from pathlib import Path
from backend.config import Settings
from backend.contracts import EvidenceBox
from backend.evidence import draw_boxes
from backend.f1.vision_types import Observation, Scene
from backend.media import extract_jpeg

video, t, out = Path(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
settings = Settings.from_env()
payload = json.load(open(sorted(glob.glob(str(settings.cache_dir / "*" / "*.json")))[-1]))
scene = Scene.model_validate(payload["scene"])
obs = min((Observation.model_validate(o) for o in payload["observations"]), key=lambda o: abs(o.timestamp_sec - t))
boxes = [EvidenceBox(label=f"scene:{name} {d.score:.2f}", box=tuple(d.box)) for name, d in scene.objects.items()]
boxes += [EvidenceBox(label=f"{d.track_id} {d.score:.2f}", box=tuple(d.box)) for d in obs.detections]
for b in boxes:
    print(b.label, [round(v, 3) for v in b.box])
out.write_bytes(draw_boxes(extract_jpeg(video, obs.timestamp_sec), boxes))
print("wrote", out, "at t =", obs.timestamp_sec)
