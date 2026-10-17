"""Stage 2: turn tracked people + scene geometry into ANCHOR events (no rule decisions).

Geometry comes from the per-video OWLv2 scene boxes, never from fixed pixels. The laptop is the most
reliable landmark of the cashier's workplace in overhead views; the OWLv2 "desk" box is used only when it
is plausible (large enough and touching the laptop), otherwise the desk region is the padded union of the
laptop and counting-machine boxes.

Per sampled frame:
  at_laptop  - a person box overlaps the laptop zone (the cashier at the workplace)
  at_safe    - a person box overlaps the safe box
  others     - people near the workplace who are not the at-laptop person (clients, collectors, visitors)
  staff_zone - people overlapping the laptop or safe zone (2+ = someone besides the cashier on the cashier side)
  room       - all tracked people
Counts are median-smoothed over SMOOTH_SEC; a change persisting MIN_HOLD seconds is an anchor.
"""
import numpy as np

SMOOTH_SEC = 1.0
MIN_HOLD = 1.0
MERGE_SEC = 0.8
LAPTOP_PAD = 0.05
WORK_PAD = 0.10


def _center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _inter(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _pad(b, p):
    return [max(0, b[0] - p), max(0, b[1] - p), min(1, b[2] + p), min(1, b[3] + p)]


def _union(bs):
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def scene_geometry(det):
    sc = det["scene"]
    lap = sc.get("laptop", {}).get("box")
    cnt = sc.get("counter", {}).get("box")
    cands = [d for d in det.get("scene_candidates", []) if d["label"] == "desk"]
    desk = None
    if lap is not None:
        ok = [d for d in cands if _area(d["box"]) > 0.02 and _inter(_pad(d["box"], 0.05), lap) > 0]
        if ok:
            desk = max(ok, key=lambda d: d["score"])["box"]
    parts = [b for b in (lap, cnt, desk) if b is not None]
    workplace = _pad(_union(parts), WORK_PAD) if parts else [0, 0, 1, 1]
    regions = {"desk": {"box": _pad(_union(parts), 0.04) if parts else [0, 0, 1, 1]}}
    for k in ("laptop", "safe", "door", "counter"):
        if k in sc:
            regions[k] = {"box": sc[k]["box"]}
    return {"laptop": lap, "safe": sc.get("safe", {}).get("box"), "workplace": workplace,
            "regions": regions, "has_laptop": lap is not None}


def frame_counts(det, geo):
    lapz = _pad(geo["laptop"], LAPTOP_PAD) if geo["laptop"] else None
    safe = geo["safe"]
    rows = []
    for s in det["samples"]:
        ppl = []
        for p in s["people"]:
            b = p["box"]
            at_l = bool(lapz) and _inter(b, lapz) > 0.15 * _area(lapz)
            at_s = bool(safe) and _inter(b, safe) > 0.25 * _area(safe)
            near_w = _inter(b, geo["workplace"]) > 0.2 * _area(b)
            ppl.append({"tid": p["tid"], "box": b, "at_laptop": at_l, "at_safe": at_s, "near_work": near_w})
        n_l = sum(p["at_laptop"] for p in ppl)
        rows.append({
            "t": s["t"], "people": ppl,
            "at_laptop": int(n_l > 0),
            "at_safe": int(any(p["at_safe"] for p in ppl)),
            "others": sum(1 for p in ppl if p["near_work"] and not p["at_laptop"] and not p["at_safe"]),
            "staff_zone": sum(1 for p in ppl if p["at_laptop"] or p["at_safe"]),
            "room": len(ppl),
        })
    return rows


def _smooth(x, k):
    k = max(1, k | 1)
    pad = k // 2
    xp = np.pad(np.asarray(x, float), pad, mode="edge")
    return np.array([np.median(xp[i:i + k]) for i in range(len(x))]).round().astype(int)


def _changes(t, x, hold_n):
    out, cur = [], x[0]
    for i in range(1, len(x)):
        if x[i] != cur and all(x[j] == x[i] for j in range(i, min(len(x), i + hold_n))):
            out.append((float(t[i]), int(cur), int(x[i])))
            cur = x[i]
    return out


SERIES = ("at_laptop", "at_safe", "others", "staff_zone", "room")


def extract_anchors(det, periodic_sec=None):
    geo = scene_geometry(det)
    rows = frame_counts(det, geo)
    fps = det["sample_fps"]
    t = [r["t"] for r in rows]
    k = int(round(SMOOTH_SEC * fps))
    hold = int(round(MIN_HOLD * fps))
    series = {key: _smooth([r[key] for r in rows], k) for key in SERIES}
    anchors = []
    for key, x in series.items():
        for tt, a, b in _changes(t, x, hold):
            anchors.append({"t": round(tt, 2), "kind": f"{key}_{'up' if b > a else 'down'}", "before": a, "after": b})
    if periodic_sec:
        for tt in np.arange(periodic_sec / 2, det["duration"], periodic_sec):
            anchors.append({"t": round(float(tt), 2), "kind": "periodic", "before": None, "after": None})
    anchors.sort(key=lambda a: a["t"])
    return anchors, geo, rows, {k2: v.tolist() for k2, v in series.items()}


def merge_anchor_times(anchors, gap=MERGE_SEC):
    out = []
    for a in sorted((a for a in anchors if a["kind"] != "periodic"), key=lambda a: a["t"]):
        if out and a["t"] - out[-1]["t_last"] <= gap:
            out[-1]["kinds"].append(a["kind"])
            out[-1]["t_last"] = a["t"]
        else:
            out.append({"t": a["t"], "t_last": a["t"], "kinds": [a["kind"]]})
    return out
