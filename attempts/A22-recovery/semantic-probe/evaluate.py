"""Evaluation only: frame-presence compatibility; never imported by the pilot."""

import collections
import json
import statistics
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text())
labels = json.loads((Path(__file__).parent / "evaluation-labels.json").read_text())["cases"]
report = {
    "queries": len(rows),
    "answers": dict(collections.Counter(r["answer"] for r in rows)),
    "errors": sum(r["status"] != "ok" for r in rows),
    "unknowns": sum(r["answer"] == "unknown" for r in rows),
}
times = [r["inference_sec"] for r in rows if "inference_sec" in r]
report["latency"] = {
    "measured_queries": len(times),
    "total_sec": sum(times),
    "median_sec": statistics.median(times) if times else None,
}
for label, answer in [("cash", "banknotes"), ("id_card", "id_card")]:
    counts = collections.Counter()
    for case in labels:
        truth = case["expected"].get(label)
        if type(truth) is not bool:
            continue
        selected = [r for r in rows if r["clip"] == case["clip"] and r["t"] == case["t"]]
        accepted = any(r["answer"] == answer and r["status"] == "ok" for r in selected)
        if truth:
            counts[
                "positive_frames_with_retained_proposal"
                if accepted
                else "positive_frames_without_retained_proposal"
            ] += 1
        else:
            counts[
                "negative_frames_with_retained_proposal"
                if accepted
                else "negative_frames_without_retained_proposal"
            ] += 1
    report[label] = dict(counts)
x40 = [r for r in rows if r["clip"] == "X-40" and r["source"] == "owlv2_native128"]
report["confirmed_negative_X40"] = {
    "queries": len(x40),
    "answers": [r["answer"] for r in x40],
    "decisively_rejected": bool(x40)
    and all(
        r["status"] == "ok" and r["answer"] not in {"banknotes", "id_card", "unknown"} for r in x40
    ),
}
report["limits"] = (
    "Frame labels do not establish target-box correctness. Missing/rejected proposals do not prove "
    "frame or interval absence. All40publicclips influenced development; not held out."
)
print(json.dumps(report, indent=2))
