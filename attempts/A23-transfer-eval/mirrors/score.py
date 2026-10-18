"""Score allowlisted exports only; no API, image, model, or rule execution."""

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

BASE = Path("/home/ubuntu/workspaces/datathon26-workers/shared/a23/base")
sys.dont_write_bytecode = True
sys.path.insert(0, str(BASE))
from eval.audit_findings import normalize_prediction, number, outcome  # noqa: E402


def completed(raw):
    if raw is None:
        return {"state": "missing", "verdict": None, "runtime_s": None, "unknown_count": None}
    if not isinstance(raw, dict):
        return {"state": "invalid", "verdict": None, "runtime_s": None, "unknown_count": None}
    if raw.get("status") not in {"done", "failed"}:
        return {
            "state": raw.get("status")
            if raw.get("status") in {"queued", "processing", "unknown"}
            else "invalid",
            "verdict": None,
            "runtime_s": None,
            "unknown_count": None,
        }
    if raw["status"] == "done" and raw.get("verdict") not in {"violation", "no_violation"}:
        return {"state": "unknown", "verdict": None, "runtime_s": None, "unknown_count": None}
    try:
        if any(k in raw for k in ["findings", "violations", "ranked_findings"]):
            value = normalize_prediction(raw)
        else:
            runtime = raw.get("runtime_s", raw.get("wall_s"))
            if runtime is not None and (not number(runtime) or runtime < 0):
                raise ValueError("invalid runtime")
            if "runtime_s" in raw and "wall_s" in raw and raw["runtime_s"] != raw["wall_s"]:
                raise ValueError("conflicting runtime")
            value = {
                "state": raw["status"],
                "verdict": raw["verdict"] if raw["status"] == "done" else None,
                "runtime_s": runtime,
                "findings": None,
            }
        unknown = raw.get("unknown_count")
        if unknown is not None and (type(unknown) is not int or unknown < 0):
            raise ValueError("invalid unknown_count")
        value["unknown_count"] = unknown
        return value
    except (ValueError, TypeError, KeyError):
        return {"state": "invalid", "verdict": None, "runtime_s": None, "unknown_count": None}


def score(manifest, truth, mirrors, originals):
    cases = {c["file"]: c for c in truth["cases"]}
    if len(cases) != len(truth["cases"]) or set(cases) != {i["file"] for i in manifest["inputs"]}:
        raise ValueError("truth must match unique manifest inputs exactly")
    if not isinstance(mirrors, dict) or not isinstance(originals, dict):
        raise ValueError("exports must be explicit filename/id keyed objects")
    if set(mirrors) - set(cases):
        raise ValueError("unexpected mirror input")
    counts = Counter(dict.fromkeys(["TP", "FN", "FP", "TN"], 0))
    rows = []
    for item in manifest["inputs"]:
        expected = cases[item["file"]]["expected_verdict"]
        if expected not in {"violation", "no_violation"}:
            raise ValueError("invalid scoring truth")
        current = completed(mirrors.get(item["file"]))
        original = completed(originals.get(item["original_id"]))
        result = outcome(current["verdict"], expected, current["state"])
        if current["state"] == "done":
            counts[result] += 1
        paired = current["state"] == original["state"] == "done"
        checks = cases[item["file"]].get("human_mechanism_checks", {})

        def reasons(prediction, checks):
            return [
                {
                    "rule_id": f["rule_id"],
                    "t": f["t"],
                    "mechanism_status": checks.get(f["rule_id"], {}).get("status", "unknown"),
                    "observation": checks.get(f["rule_id"], {}).get("observation"),
                    "timing_status": "unverified",
                    "legal_status": "unverified",
                }
                for f in prediction.get("findings") or []
            ]

        rows.append(
            {
                "file": item["file"],
                "original_id": item["original_id"],
                "expected_verdict": expected,
                "mirror": current,
                "mirror_reason_checks": reasons(current, checks),
                "original_reason_checks": reasons(original, checks),
                "original": original,
                "outcome": result,
                "paired_verdict_changed": current["verdict"] != original["verdict"]
                if paired
                else None,
                "paired_outcome_before": outcome(original["verdict"], expected, original["state"])
                if paired
                else None,
                "paired_runtime_delta_s": current["runtime_s"] - original["runtime_s"]
                if paired and current["runtime_s"] is not None and original["runtime_s"] is not None
                else None,
            }
        )
    valid = sum(counts.values())
    times = [r["mirror"]["runtime_s"] for r in rows if r["mirror"]["runtime_s"] is not None]
    return {
        "unique_inputs": len(rows),
        "confusion": dict(counts),
        "accuracy_denominator": valid,
        "correct": counts["TP"] + counts["TN"],
        "accuracy": (counts["TP"] + counts["TN"]) / valid if valid else None,
        "excluded": [
            {"file": r["file"], "state": r["mirror"]["state"]}
            for r in rows
            if r["mirror"]["state"] != "done"
        ],
        "unknown_count_total_known": sum(
            r["mirror"]["unknown_count"] for r in rows if r["mirror"]["unknown_count"] is not None
        ),
        "unknown_count_missing_inputs": [
            r["file"] for r in rows if r["mirror"]["unknown_count"] is None
        ],
        "runtime": {
            "measured_inputs": len(times),
            "total_s": sum(times),
            "median_s": statistics.median(times) if times else None,
            "max_s": max(times) if times else None,
        },
        "paired_complete": sum(r["paired_verdict_changed"] is not None for r in rows),
        "paired_changes": [r["file"] for r in rows if r["paired_verdict_changed"] is True],
        "rows": rows,
        "reason_status": (
            "CSV norm/reasons unverified; no reason accuracy inferred from verdict/time"
        ),
        "limits": (
            "Inherited hflip labels, not independent held-out/new-angle evidence; "
            "failed/missing/unknown jobs excluded from accuracy, never clean."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["manifest", "truth", "mirrors", "originals", "out"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    result = score(
        *[
            json.loads(getattr(args, key).read_text())
            for key in ["manifest", "truth", "mirrors", "originals"]
        ]
    )
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
