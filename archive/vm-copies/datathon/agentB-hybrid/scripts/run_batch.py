"""Run probes (VLM at anchors) for clips of a split; caches answers per clip. Prints aggregates only."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid import vlm, engine  # noqa: E402
from hybrid.anchors import extract_anchors  # noqa: E402

G = "/home/ubuntu/dt26-validation/data/validation-private/"
gt = json.load(open(G + "gt.json")); sp = json.load(open(G + "split.json"))
which = sys.argv[1]
cache = Path("cache")
vlm.set_cache(str(cache / "_vlm_cache"))
ids = [k for k in gt if which == "all" or sp[k] == which] if which in ("dev", "lockbox", "all") else which.split(",")
for k in ids:
    det = json.load(open(cache / k / "det.json"))
    t0 = time.time()
    anchors, geo, rows, series = extract_anchors(det, periodic_sec=engine.PERIODIC_SEC)
    det["_geo"] = geo
    st = engine.structure(anchors, det)
    P = engine.plan(st, det)
    A = engine.run_probes(P, det, str(cache / k / "frames"))
    wall = time.time() - t0
    errs = sum(1 for r in A.values() if r["err"])
    json.dump({"answers": {f"{i}|{g}": r for (i, g), r in A.items()}, "probe_wall_s": wall,
               "n_calls": len(A), "errors": errs}, open(cache / k / "answers.json", "w"))
    print(f"{k} calls={len(A)} errors={errs} probe_wall={wall:.1f}s det={det['detect_s']:.1f}s", flush=True)
