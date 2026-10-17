"""Aggregate anchor recall vs organizer label times (prints aggregates only)."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid.anchors import extract_anchors, merge_anchor_times  # noqa: E402

gt = json.load(open(sys.argv[1]))
split = json.load(open(sys.argv[2]))
cache = Path(sys.argv[3])
which = sys.argv[4] if len(sys.argv) > 4 else "all"
ids = [k for k in gt if which == "all" or split[k] == which]
hits = collections.Counter()
n_lab = 0
per_kind_hit = collections.Counter()
clean_counts, viol_counts = [], []
kind_clean = collections.Counter()
missed = 0
for k in ids:
    det = json.load(open(cache / k / "det.json"))
    anchors, geo, rows, series = extract_anchors(det)
    merged = merge_anchor_times(anchors)
    (viol_counts if gt[k]["violation"] else clean_counts).append(len(merged))
    if not gt[k]["violation"]:
        for a in anchors:
            kind_clean[a["kind"]] += 1
    for lt in gt[k]["org_times"]:
        n_lab += 1
        for tau in (1, 2, 3):
            if any(abs(a["t"] - lt) <= tau for a in anchors):
                hits[tau] += 1
        for a in anchors:
            if abs(a["t"] - lt) <= 2:
                per_kind_hit[a["kind"]] += 1
print(f"split={which} labels={n_lab} recall ±1s {hits[1]}/{n_lab} ±2s {hits[2]}/{n_lab} ±3s {hits[3]}/{n_lab}")
import statistics as st  # noqa: E402
print(f"merged anchors per clean clip: mean {st.mean(clean_counts):.1f} median {st.median(clean_counts)} max {max(clean_counts)}; "
      f"per violation clip mean {st.mean(viol_counts):.1f}")
print("anchor kinds within ±2s of a label:", dict(per_kind_hit))
print("anchor kinds on clean clips (count):", dict(kind_clean))
