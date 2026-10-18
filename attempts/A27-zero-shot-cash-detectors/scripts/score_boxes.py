#!/usr/bin/env python3
"""Score each model's top box against the human box review from label_server.py.

    python score_boxes.py --out ~/a27_out   # reads results.json + box-labels.json, writes box-score.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from label_server import candidates
from run import DEFAULT_THRESHOLDS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    results = json.loads((args.out / "results.json").read_text())["results"]
    labels = json.loads((args.out / "box-labels.json").read_text())
    frames = list(dict.fromkeys(f"{r['clip']}@{r['t']}" for r in results))
    cash_visible = {f"{r['clip']}@{r['t']}": r["cash_visible"] for r in results}

    rows, unmarked = [], []
    for key in frames:
        marks = labels.get(key, {}).get("marks", {})
        for c in candidates(results, key):
            mark = marks.get(c["id"])
            if mark is None or mark["box"] != c["box"]:
                unmarked.append(f"{key}/{c['id']}")
                continue
            for p in c["proposals"]:
                rows.append({"frame": key, "cash_visible": cash_visible[key], "model": p["model"],
                             "score": p["score"], "verdict": mark["verdict"]})
    if unmarked:
        raise SystemExit(f"unmarked or changed candidates: {unmarked}")

    models = {}
    for name in dict.fromkeys(r["model"] for r in rows):
        mine = [r for r in rows if r["model"] == name]
        thr = DEFAULT_THRESHOLDS[name]
        pos = [r for r in mine if r["cash_visible"]]
        neg = [r for r in mine if not r["cash_visible"]]
        models[name] = {
            "top_box_on_cash_frames": dict(Counter(r["verdict"] for r in pos)),
            "top_box_on_empty_frames": dict(Counter(r["verdict"] for r in neg)),
            # a frame counts as found only when the score passes the default threshold
            # and a human confirmed the box is on cash
            "localized_hits_at_threshold": sum(r["score"] >= thr and r["verdict"] == "cash" for r in pos),
            "wrong_box_above_threshold": sum(r["score"] >= thr and r["verdict"] != "cash" for r in mine),
            "threshold": thr,
            "cash_frames": len(pos),
            "per_frame": [{k: r[k] for k in ("frame", "score", "verdict")} for r in mine],
        }
    drawn = {k: len(v.get("drawn", [])) for k, v in labels.items() if v.get("drawn")}
    out = {"models": models, "missed_cash_boxes_drawn": drawn}
    (args.out / "box-score.json").write_text(json.dumps(out, indent=2))
    brief = {n: {k: v for k, v in m.items() if k != "per_frame"} for n, m in models.items()}
    print(json.dumps(brief, indent=2))
    print("missed cash drawn:", drawn)


if __name__ == "__main__":
    main()
