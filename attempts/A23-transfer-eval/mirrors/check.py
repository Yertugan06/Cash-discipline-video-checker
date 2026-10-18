"""One CPU scorer check: duplicate truth, failed jobs, unknowns and paired changes."""

import json
from pathlib import Path

from score import completed, score

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text())
truth = json.loads((root / "scoring-truth.json").read_text())
assert len(manifest["inputs"]) == 8 and sum(c["csv_rows"] for c in truth["cases"]) == 9
assert next(c for c in truth["cases"] if c["file"] == "X-4_mirror.mov")["csv_rows"] == 2
rows = {
    c["file"]: {
        "status": "done",
        "verdict": c["expected_verdict"],
        "runtime_s": 2,
        "unknown_count": 0,
    }
    for c in truth["cases"]
}
originals = {
    c["original_id"]: {"status": "done", "verdict": c["expected_verdict"], "runtime_s": 1}
    for c in truth["cases"]
}
result = score(manifest, truth, rows, originals)
assert (
    result["confusion"] == {"TP": 4, "FN": 0, "FP": 0, "TN": 4}
    and result["accuracy_denominator"] == 8
)
rows["X-5_mirror.mov"] = {"status": "failed", "verdict": "no_violation", "runtime_s": 3}
rows["X-4_mirror.mov"]["verdict"] = "unknown"
rows["X-11_mirror.mov"]["verdict"] = "no_violation"
result = score(manifest, truth, rows, originals)
assert (
    result["confusion"] == {"TP": 2, "FN": 1, "FP": 0, "TN": 3}
    and result["accuracy_denominator"] == 6
)
assert result["paired_changes"] == ["X-11_mirror.mov"]
assert {r["file"]: r["state"] for r in result["excluded"]} == {
    "X-4_mirror.mov": "unknown",
    "X-5_mirror.mov": "failed",
}
assert (
    completed({"status": "done", "verdict": "no_violation", "runtime_s": float("nan")})["state"]
    == "invalid"
)
assert completed({"verdict": "no_violation"})["state"] == "invalid"
assert completed(None)["state"] == "missing"
print(
    "PASS:8unique/9CSVrows; failed+unknown excluded; TP/FN/FP/TN; paired changes; invalid runtime"
)

rows["X-4_mirror.mov"] = {
    "status": "done",
    "verdict": "violation",
    "runtime_s": 1,
    "findings": [{"rule_id": "S-CLEAN-DESK-HANDOVER", "t": 57}],
}
result = score(manifest, truth, rows, originals)
x4 = next(r for r in result["rows"] if r["file"] == "X-4_mirror.mov")
assert x4["mirror_reason_checks"][0]["mechanism_status"] == "mechanism_compatible"
assert x4["mirror_reason_checks"][0]["timing_status"] == "unverified"
assert x4["mirror_reason_checks"][0]["legal_status"] == "unverified"
