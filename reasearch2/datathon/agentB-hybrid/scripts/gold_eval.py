"""Gold-frame field accuracy: full frame vs crop vs crop+reference (aggregates only)."""
import collections
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid import vlm  # noqa: E402
from hybrid.anchors import frame_counts, scene_geometry  # noqa: E402

gold_csv, cache = sys.argv[1], Path(sys.argv[2])
vlm.set_cache(str(cache / "_vlm_cache"))
rows = list(csv.DictReader(open(gold_csv, encoding="utf-8"), delimiter=";"))
field_group = {f: g for g, d in vlm.GROUPS.items() for f in d["fields"]}
field_group["cashier_action"] = None


def frame_at(clip, t):
    det = json.load(open(cache / clip / "det.json"))
    i = min(len(det["samples"]) - 1, round(t * det["sample_fps"]))
    return det, i, Image.open(cache / clip / "frames" / f"{i:05d}.jpg").convert("RGB")


jobs = {}
for r in rows:
    g = field_group.get(r["field"])
    if g is None:
        continue
    for mode in (["full"] if vlm.GROUPS[g]["region"] is None else ["full", "crop", "crop_ref"]):
        jobs[(r["video"], float(r["t"]), g, mode)] = None


def run(key):
    clip, t, g, mode = key
    det, i, fr = frame_at(clip, t)
    ref = Image.open(cache / clip / "frames" / "00002.jpg").convert("RGB") if mode == "crop_ref" else None
    ans, lat, err, used = vlm.ask(g, fr, scene_geometry(det)["regions"], mode=mode, ref_frame=ref)
    return key, ans, lat, err, used


with ThreadPoolExecutor(4) as ex:
    for key, ans, lat, err, used in ex.map(run, list(jobs)):
        jobs[key] = (ans, lat, err, used)


def norm(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip().lower()


acc = collections.defaultdict(lambda: collections.Counter())
fallback = collections.Counter()
lats = []
for r in rows:
    g = field_group.get(r["field"])
    if g is None:
        acc[(r["field"], "n/a")]["n"] += 1
        continue
    for mode in (["full"] if vlm.GROUPS[g]["region"] is None else ["full", "crop", "crop_ref"]):
        ans, lat, err, used = jobs[(r["video"], float(r["t"]), g, mode)]
        lats.append(lat)
        if used != mode:
            fallback[mode] += 1
        got = norm((ans or {}).get(r["field"], "NO_ANSWER"))
        acc[(r["field"], mode)]["n"] += 1
        acc[(r["field"], mode)]["ok"] += got == norm(r["value"])
    # detector-derived people fields
    if r["field"] in ("cashier_at_desk", "people_cashier_side", "clients_at_desk"):
        det, i, _ = frame_at(r["video"], float(r["t"]))
        c = frame_counts(det, scene_geometry(det))[i]
        val = {"cashier_at_desk": norm(c["at_laptop"] > 0), "people_cashier_side": str(c["staff_zone"]),
               "clients_at_desk": str(c["others"])}[r["field"]]
        acc[(r["field"], "detector")]["n"] += 1
        acc[(r["field"], "detector")]["ok"] += val == norm(r["value"])

fields = sorted({f for f, _ in acc})
modes = ["full", "crop", "crop_ref", "detector"]
print("| field | " + " | ".join(modes) + " |")
tot = collections.Counter()
for f in fields:
    cells = []
    for m in modes:
        c = acc.get((f, m))
        if c:
            cells.append(f"{c['ok']}/{c['n']}")
            tot[m + "_ok"] += c["ok"]
            tot[m + "_n"] += c["n"]
        else:
            cells.append("-")
    print(f"| {f} | " + " | ".join(cells) + " |")
print("totals:", {m: f"{tot[m + '_ok']}/{tot[m + '_n']}" for m in modes})
print("crop fallbacks to full (region not found):", dict(fallback))
nz = [x for x in lats if x > 0]
if nz:
    print(f"latency s: mean {sum(nz) / len(nz):.2f} max {max(nz):.2f} (n={len(nz)} uncached)")
