"""Per cache entry: why L-LEFT-DURING-SERVICE did or did not fire (merged code). Counts only."""
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

config = load_perception_config(ROOT / "config" / "perception.yaml")
codex = load_codex(ROOT / "config" / "f1_codex.yaml")
from backend.f1.vision_types import Observation, Scene
tot = dict(entries=0, sessions=0, entries_with_session=0, cashier_exits=0, confirmed_room_exits=0,
           exits_in_entries_with_session=0, exit_during_open_session=0, cut_by_recording_end=0, cash_suppressed=0)
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
    tot["entries"] += 1; tot["sessions"] += len(log.sessions); tot["entries_with_session"] += bool(log.sessions)
    tot["cashier_exits"] += sum(1 for e in ctx.events("EXIT") if e.facts.get("role") == "cashier")
    exits = ctx.room_exits(); tot["confirmed_room_exits"] += len(exits)
    if log.sessions: tot["exits_in_entries_with_session"] += len(exits)
    cash = [f.timestamp_sec for f in l_no_cash_on_leave(ctx)] if log.coverage.get("desk") else []
    for e in exits:
        s = e.timestamp_sec
        if any(v["start"] <= s and (v["end"] is None or v["end"] > s) for v in log.sessions.values()):
            tot["exit_during_open_session"] += 1
            tot["cut_by_recording_end"] += s + 3 > dur
            tot["cash_suppressed"] += any(s - 8 <= t <= s + 1 for t in cash)
print(json.dumps(tot))
