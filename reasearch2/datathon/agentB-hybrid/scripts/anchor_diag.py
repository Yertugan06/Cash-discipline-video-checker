"""Per-label anchor diagnostics on DEV violation clips (detector metadata only, no images/VLM text)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid.anchors import extract_anchors, SERIES
G = "/home/ubuntu/dt26-validation/data/validation-private/"
gt = json.load(open(G + "gt.json")); sp = json.load(open(G + "split.json"))
for k in gt:
    if sp[k] != "dev" or not gt[k]["violation"]:
        continue
    det = json.load(open(f"cache/{k}/det.json"))
    an, geo, rows, ser = extract_anchors(det)
    for lt in gt[k]["org_times"]:
        near = sorted(an, key=lambda a: abs(a["t"] - lt))[:4]
        print(k, lt, [(round(a["t"] - lt, 1), a["kind"]) for a in near])
        i0 = max(0, int((lt - 8) * 5)); i1 = int((lt + 8) * 5)
        for key in SERIES:
            print(f"   {key:10s}", "".join(str(v) for v in ser[key][i0:i1:2]))
