"""Apply rules to cached anchors+answers, write scorer preds and per-rule dev stats (aggregates only)."""
import collections, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid import engine  # noqa: E402
from hybrid.anchors import extract_anchors  # noqa: E402
from hybrid.codex import scorer_code  # noqa: E402

G = "/home/ubuntu/dt26-validation/data/validation-private/"
gt = json.load(open(G + "gt.json")); sp = json.load(open(G + "split.json"))
name, which = sys.argv[1], sys.argv[2]
enabled = set(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] != "all" else None
cache = Path("cache")
ids = [k for k in gt if which == "all" or sp[k] == which]
preds, stats = {}, collections.defaultdict(collections.Counter)
for k in ids:
    det = json.load(open(cache / k / "det.json"))
    a = json.load(open(cache / k / "answers.json"))
    A = {(int(key.split("|")[0]), key.split("|")[1]): v for key, v in a["answers"].items()}
    anchors, geo, rows, series = extract_anchors(det, periodic_sec=engine.PERIODIC_SEC)
    st = engine.structure(anchors, det)
    ev = engine.apply_rules(st, det, A, enabled)
    preds[k] = {"verdict": "violation" if ev else "no_violation",
                "events": [{"t": e["t"], "code": scorer_code(e["codex"]), "conf": e["conf"]} for e in ev],
                "runtime_s": round(det["detect_s"] + a["probe_wall_s"], 1), "error": None}
    y = gt[k]["violation"]
    for r in {e["rule"] for e in ev}:
        near = y and any(abs(e["t"] - t) <= 3 for e in ev if e["rule"] == r for t in gt[k]["org_times"])
        stats[r]["fires_viol_clip" if y else "fires_clean_clip"] += 1
        stats[r]["hit_pm3"] += near
out = Path("score_root/data/validation-private/preds"); out.mkdir(parents=True, exist_ok=True)
json.dump(preds, open(out / f"B_{name}.json", "w"), indent=1)
Path("preds").mkdir(exist_ok=True)
json.dump(preds, open(f"preds/B_{name}.json", "w"), indent=1)
print("rule | fires on violation clips | of which within ±3s of a label | fires on clean clips")
for r in sorted(stats):
    s = stats[r]; print(f"{r} | {s['fires_viol_clip']} | {s['hit_pm3']} | {s['fires_clean_clip']}")
