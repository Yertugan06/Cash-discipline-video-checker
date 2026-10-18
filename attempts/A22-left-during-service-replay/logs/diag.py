"""Per clip: why L-LEFT-DURING-SERVICE did or did not fire. Counts only."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/work")
from backend.config import ROOT
from backend.f1.calibration import calibrate
from backend.f1.codex import load_codex
from backend.f1.detector import FPS
from backend.f1.events import build_events
from backend.f1.perception import load_perception_config
from backend.f1.rules import Context, l_no_cash_on_leave
from backend.f1.vision_types import Observation, Scene

config = load_perception_config(ROOT / "config" / "perception.yaml")
codex = load_codex(ROOT / "config" / "f1_codex.yaml")
tot = dict(clips=0, leaves=0, leaves_3s=0, exited=0, open_session=0, exited_and_open=0, cash_suppressed=0, cashier_exits=0, sessions=0, roles_cov=0)
for d in sorted(p for p in Path("/app/runtime/perception_cache").iterdir() if p.is_dir()):
    files = list(d.glob("*.json"))
    if not files: continue
    payload = json.loads(max(files, key=lambda p: p.stat().st_mtime).read_text())
    scene = Scene.model_validate(payload["scene"])
    if scene.candidates:
        scene = calibrate(scene.candidates, ROOT / "config" / "overrides.yaml", d.name)
    obs = [Observation.model_validate(o) for o in payload["observations"]]
    dur = obs[-1].timestamp_sec + 1 / FPS
    log = build_events(scene, obs, config, FPS, dur)
    ctx = Context(codex, log, obs, scene, dur)
    tot["clips"] += 1; tot["roles_cov"] += bool(log.coverage.get("roles"))
    tot["sessions"] += len(log.sessions)
    tot["cashier_exits"] += sum(1 for e in ctx.events("EXIT") if e.facts.get("role") == "cashier")
    cash = [f.timestamp_sec for f in l_no_cash_on_leave(ctx)] if log.coverage.get("desk") else []
    tot["leaves"] += len(ctx.leaves())
    for leave in ctx.leaves(minimum_away=3.0):
        tot["leaves_3s"] += 1
        s = leave.timestamp_sec
        end = next((e.timestamp_sec + du for e, du in ctx.intervals("WORKSTATION_AWAY") if e.timestamp_sec <= s <= e.timestamp_sec + du), dur)
        ex = leave.type == "EXIT" or ctx.has_event("EXIT", s, end, role="cashier")
        op = any(v["start"] <= s and (v["end"] is None or v["end"] > s) for v in log.sessions.values())
        tot["exited"] += ex; tot["open_session"] += op; tot["exited_and_open"] += ex and op
        tot["cash_suppressed"] += ex and op and any(abs(t - s) < 1 for t in cash)
        rel = []
        for v in log.sessions.values():
            if s < v["start"]: rel.append(("before_start", round(v["start"] - s, 1)))
            elif v["end"] is not None and s >= v["end"]: rel.append(("after_end", round(s - v["end"], 1)))
        rel.sort(key=lambda r: r[1])
        key = rel[0][0] if rel else "no_session_in_clip"
        tot.setdefault("rel", {}).setdefault(key, []).append(rel[0][1] if rel else None)
print(json.dumps(tot))
