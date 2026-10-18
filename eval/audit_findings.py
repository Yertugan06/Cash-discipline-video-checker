"""Independent, CPU-only audit of pinned replay/API text, never videos or image fields.

First pin explicit inputs, then run the manifest; no directory/newest-cache discovery:

    python -m eval.audit_findings pin --labels data/prepared/videos.jsonl \
        --predictions replay.jsonl --assertions observations.json --out inputs.json
    python -m eval.audit_findings run --manifest inputs.json --out audit.json \
        --markdown audit.md

Manifest paths are relative to --root (the repository by default). For a single full API
job without a SHA, supply --clip X-20 when pinning. Multiple predictions files may be
listed explicitly. Conflicting records for one SHA are rejected, never chosen by mtime.
This validates audit-relevant fields, not the complete API/evidence-image contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from backend.clip_id import clip_number, parse_clip_id
from eval.data import sha256_file

ROOT = Path(__file__).resolve().parent.parent
VERDICTS = {"violation", "no_violation"}
REASON_STATUSES = {"supported", "contradicted", "unknown"}
SHA = re.compile(r"[a-f0-9]{64}")


def number(value: object) -> bool:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def pin_file(path: Path, root: Path) -> dict:
    path = path.resolve()
    # The audit handles only textual inputs. In particular, do not hash/read video frames.
    if path.suffix not in {".json", ".jsonl", ".py", ".yaml", ".md"}:
        raise ValueError("only explicit JSON/JSONL or text reference files may be pinned")
    return {
        "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def make_manifest(labels: Path, predictions: list[Path], assertions: Path, root: Path) -> dict:
    return {
        "schema_version": 1,
        "path_base": "explicit --root; defaults to repository root",
        "labels": pin_file(labels, root),
        "predictions": [pin_file(path, root) for path in predictions],
        "assertions": pin_file(assertions, root),
        "references": [],
    }


def read_pinned(entry: dict, root: Path) -> str:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError("manifest input must contain a path")
    expected = entry.get("sha256")
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise ValueError("manifest input must contain a SHA-256")
    path = (root / entry["path"]).resolve()
    if path.suffix not in {".json", ".jsonl", ".py", ".yaml", ".md"}:
        raise ValueError("pinned input is not a supported text file")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f"pinned input hash mismatch: {entry['path']}")
    return payload.decode("utf-8")


def read_records(payload: str, source: str) -> tuple[list[dict], list[dict]]:
    """JSON object/array or JSONL; errors contain locations, never copied payloads/images."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        records, errors = [], []
        for line, text in enumerate(payload.splitlines(), 1):
            if not text.strip():
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                errors.append({"source": source, "record": line, "error": "invalid JSON"})
                continue
            if not isinstance(value, dict):
                errors.append({"source": source, "record": line, "error": "not an object"})
            else:
                records.append({"raw": value, "source": source, "record": line})
        return records, errors
    values = parsed if isinstance(parsed, list) else [parsed]
    records, errors = [], []
    for index, value in enumerate(values, 1):
        if not isinstance(value, dict):
            errors.append({"source": source, "record": index, "error": "not an object"})
        else:
            records.append({"raw": value, "source": source, "record": index})
    return records, errors


def load_labels(payload: str) -> tuple[dict[str, list[dict]], dict[str, str]]:
    records, errors = read_records(payload, "labels")
    if errors or not records:
        raise ValueError("labels must contain nonempty, valid JSON records")
    groups, by_clip = defaultdict(list), {}
    for item in records:
        row = item["raw"]
        sha = row.get("sha256")
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError("label has invalid SHA-256")
        clip = parse_clip_id(row.get("original_id") or row.get("video_id") or "")
        if clip in by_clip:
            raise ValueError(f"duplicate label row for {clip}")
        verdict, times, duration = (
            row.get("organizer_verdict"),
            row.get("organizer_timestamps"),
            row.get("duration_sec"),
        )
        if not isinstance(verdict, str) or verdict not in VERDICTS:
            raise ValueError("label has invalid organizer verdict")
        if not isinstance(times, list) or any(not number(t) or t < 0 for t in times):
            raise ValueError("label has invalid organizer timestamps")
        if not number(duration) or duration <= 0 or any(t > duration for t in times):
            raise ValueError("label has invalid duration/timestamps")
        by_clip[clip] = sha
        groups[sha].append(
            {
                "clip_id": clip,
                "verdict": verdict,
                "timestamps_sec": times,
                "duration_sec": duration,
                "provenance": row.get("label_provenance"),
            }
        )
    for files in groups.values():
        files.sort(key=lambda row: clip_number(row["clip_id"]))
    return dict(groups), by_clip


def validate_assertions(document: dict, by_clip: dict[str, str]) -> dict[str, dict]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("unsupported assertions schema")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("id") or not provenance.get("kind"):
        raise ValueError("assertions require explicit provenance")
    groups = {}
    for assertion in document.get("clips", []):
        if not isinstance(assertion, dict) or not assertion.get("clip_ids"):
            raise ValueError("assertion must identify clips")
        shas = {by_clip[parse_clip_id(clip)] for clip in assertion["clip_ids"]}
        if len(shas) != 1:
            raise ValueError("one assertion may cover only one SHA group")
        sha = shas.pop()
        if sha in groups:
            raise ValueError("duplicate assertion for SHA group")
        if assertion.get("provenance_id") != provenance["id"]:
            raise ValueError("assertion provenance does not match its document")
        events = assertion.get("events", [])
        event_ids = {event["id"] for event in events}
        if len(event_ids) != len(events):
            raise ValueError("duplicate event ID")
        for event in events:
            interval = event.get("interval_sec")
            if interval is not None and (
                not isinstance(interval, list)
                or len(interval) != 2
                or not all(number(t) and t >= 0 for t in interval)
                or interval[0] > interval[1]
            ):
                raise ValueError("invalid human event interval")
        rules = set()
        for check in assertion.get("reason_checks", []):
            if check.get("status") not in REASON_STATUSES or not check.get("explanation"):
                raise ValueError("reason check needs a status and explanation")
            if not set(check.get("event_ids", [])) <= event_ids:
                raise ValueError("reason check refers to unknown human event")
            for rule in check.get("rule_ids", []):
                if rule in rules:
                    raise ValueError("conflicting/repeated reason check")
                rules.add(rule)
        groups[sha] = assertion
    return groups


def prediction_sha(raw: dict, clip_hint: str | None, by_clip: dict[str, str]) -> str:
    sha = raw.get("sha256")
    clip = raw.get("clip_id") or raw.get("name") or clip_hint
    if clip is not None:
        if not isinstance(clip, str):
            raise ValueError("invalid clip identity")
        try:
            clip = parse_clip_id(clip)
        except ValueError:
            raise ValueError("invalid clip identity") from None
        if clip not in by_clip:
            raise ValueError("prediction clip has no label")
        if sha is not None and sha != by_clip[clip]:
            raise ValueError("prediction clip and SHA disagree")
        sha = by_clip[clip]
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("prediction needs SHA-256 or an explicit labelled clip identity")
    return sha


def normalize_prediction(raw: dict) -> dict:
    runtime = raw.get("runtime_s", raw.get("wall_s"))
    if runtime is not None and (not number(runtime) or runtime < 0):
        raise ValueError("invalid runtime")
    if "runtime_s" in raw and "wall_s" in raw and raw["runtime_s"] != raw["wall_s"]:
        raise ValueError("conflicting runtime fields")
    if raw.get("status") == "failed":
        return {"state": "failed", "verdict": None, "findings": [], "runtime_s": runtime}
    if raw.get("status", "done") != "done":
        raise ValueError("prediction is not a completed/failed result")
    if "findings" in raw and "violations" in raw:
        raise ValueError("ambiguous findings and violations fields")
    # Ranked replay output is the service-visible result; raw candidates are not extra findings.
    field = next((key for key in ("ranked_findings", "findings", "violations") if key in raw), None)
    if field is None or not isinstance(raw[field], list):
        raise ValueError("prediction must contain a findings/violations list")
    findings = []
    for finding in raw[field]:
        if not isinstance(finding, dict):
            raise ValueError("finding must be an object")
        rule, t = finding.get("rule_id"), finding.get("t", finding.get("timecode_sec"))
        if not isinstance(rule, str) or not rule.strip() or rule != rule.strip():
            raise ValueError("finding needs a nonempty rule_id")
        if not number(t) or t < 0:
            raise ValueError("finding has invalid timestamp")
        # Never copy description/evidence/image fields into the audit.
        item = {"rule_id": rule, "t": t}
        if isinstance(finding.get("citation_status"), str):
            item["reported_citation_status"] = finding["citation_status"]
        findings.append(item)
    inferred = "violation" if findings else "no_violation"
    verdict = raw.get("verdict", inferred)
    if not isinstance(verdict, str) or verdict not in VERDICTS or verdict != inferred:
        raise ValueError("invalid verdict or verdict/findings inconsistency")
    return {
        "state": "done",
        "verdict": verdict,
        "verdict_source": "explicit" if "verdict" in raw else "derived_from_findings",
        "findings": findings,
        "findings_source": field,
        "runtime_s": runtime,
    }


def reason_audit(finding: dict, assertion: dict | None, files: list[dict]) -> dict:
    check = next(
        (
            check
            for check in (assertion or {}).get("reason_checks", [])
            if finding["rule_id"] in check["rule_ids"]
        ),
        None,
    )
    status = check["status"] if check else "unknown"
    result = {
        **finding,
        "reason_status": status,
        "explanation": check["explanation"]
        if check
        else "No supplied event-level reason assertion.",
        "provenance_id": assertion["provenance_id"] if check else None,
        "legal_policy_status": "pending_source_review",
        "compatible_event_timing": [],
        # Keep EVERY duplicate's markers; this descriptive offset never changes reason status.
        "organizer_offsets": [
            {
                "clip_id": f["clip_id"],
                "timestamps_sec": f["timestamps_sec"],
                "signed_offsets_sec": [round(finding["t"] - t, 3) for t in f["timestamps_sec"]],
                "eligible_for_compatible_timing": status == "supported",
            }
            for f in files
        ],
    }
    if status == "supported":
        events = {event["id"]: event for event in assertion.get("events", [])}
        for event_id in check.get("event_ids", []):
            interval = events[event_id].get("interval_sec")
            delta = (
                None
                if interval is None
                else max(interval[0] - finding["t"], 0, finding["t"] - interval[1])
            )
            result["compatible_event_timing"].append(
                {
                    "event_id": event_id,
                    "human_interval_sec": interval,
                    "absolute_distance_to_interval_sec": round(delta, 3)
                    if delta is not None
                    else None,
                }
            )
    return result


def outcome(verdict: str | None, actual: str, state: str) -> str:
    if state != "done":
        return state
    return (
        ("TP" if actual == "violation" else "FP")
        if verdict == "violation"
        else ("FN" if actual == "violation" else "TN")
    )


def audit(
    labels_text: str,
    prediction_inputs: list[tuple[dict, str]],
    assertions: dict,
) -> dict:
    labels, by_clip = load_labels(labels_text)
    observed = validate_assertions(assertions, by_clip)
    predictions, invalid_by_sha, errors = defaultdict(list), defaultdict(list), []
    input_count, unlabelled = 0, []
    for entry, payload in prediction_inputs:
        records, parse_errors = read_records(payload, entry["path"])
        input_count += len(records) + len(parse_errors)
        errors.extend(parse_errors)
        for record in records:
            raw, sha = record["raw"], None
            location = {"source": record["source"], "record": record["record"]}
            try:
                sha = prediction_sha(raw, entry.get("clip_id"), by_clip)
                normalized = normalize_prediction(raw)
                if sha in labels and any(
                    f["t"] > min(row["duration_sec"] for row in labels[sha])
                    for f in normalized["findings"]
                ):
                    raise ValueError("finding timestamp exceeds video duration")
            except ValueError as exc:
                # Error strings are our fixed validation messages, never serialized raw records.
                error = {**location, "sha256": sha, "error": str(exc)}
                errors.append(error)
                if sha:
                    invalid_by_sha[sha].append(error)
                continue
            if sha not in labels:
                unlabelled.append({**location, "sha256": sha})
            else:
                predictions[sha].append({**normalized, **location})
    unique_counts = Counter(
        {
            key: 0
            for key in ("TP", "FN", "FP", "TN", "missing", "invalid", "failed", "label_conflict")
        }
    )
    sample_counts, reasons, clips, runtimes = unique_counts.copy(), Counter(), [], []
    duplicate_prediction_records, conflicts = 0, 0
    for sha, files in sorted(labels.items(), key=lambda item: clip_number(item[1][0]["clip_id"])):
        candidates = predictions.get(sha, [])
        duplicate_prediction_records += max(0, len(candidates) - 1)
        signatures = {
            json.dumps({key: p[key] for key in ("state", "verdict", "findings")}, sort_keys=True)
            for p in candidates
        }
        if len(signatures) > 1:
            conflicts += 1
            errors.append({"sha256": sha, "error": "conflicting predictions for identical SHA"})
        state = (
            "invalid"
            if invalid_by_sha[sha] or len(signatures) > 1
            else (candidates[0]["state"] if candidates else "missing")
        )
        prediction = candidates[0] if state in {"done", "failed"} else None
        verdict = prediction["verdict"] if prediction else None
        actual = {f["verdict"] for f in files}
        unique_outcome = (
            outcome(verdict, next(iter(actual)), state) if len(actual) == 1 else ("label_conflict")
        )
        unique_counts[unique_outcome] += 1
        sample_outcomes = []
        for f in files:
            sample_outcome = outcome(verdict, f["verdict"], state)
            sample_counts[sample_outcome] += 1
            sample_outcomes.append({"clip_id": f["clip_id"], "outcome": sample_outcome})
        assertion = observed.get(sha)
        findings = [
            reason_audit(f, assertion, files)
            for f in (prediction["findings"] if prediction else [])
        ]
        reasons.update(f["reason_status"] for f in findings)
        timings = [
            {"source": p["source"], "record": p["record"], "runtime_s": p["runtime_s"]}
            for p in candidates
        ]
        runtimes.extend(t["runtime_s"] for t in timings if t["runtime_s"] is not None)
        clips.append(
            {
                "sha256": sha,
                "clip_ids": [f["clip_id"] for f in files],
                "organizer_files": files,
                "organizer_label_conflict": len(actual) > 1,
                "prediction_state": state,
                "predicted_verdict": verdict,
                "unique_outcome": unique_outcome,
                "sample_outcomes": sample_outcomes,
                "prediction_records": len(candidates),
                "findings_source": prediction.get("findings_source") if prediction else None,
                "findings": findings,
                "runtime_records": timings,
                "human_annotation_coverage": assertion.get("coverage", "partial")
                if assertion
                else "missing",
                "human_observation": assertion,
                "reason_audit_failures": sum(
                    f["reason_status"] == "contradicted" for f in findings
                ),
                "legal_policy_status": "pending_source_review",
            }
        )
    covered = len(observed)
    compatible_timings = [
        timing
        for clip in clips
        for finding in clip["findings"]
        for timing in finding["compatible_event_timing"]
    ]
    return {
        "schema_version": 1,
        "scope": "Retrospective audit only; no model inference or runtime rule changes.",
        "summary": {
            "organizer_samples": len(by_clip),
            "unique_sha_groups": len(labels),
            "duplicate_samples": len(by_clip) - len(labels),
            "duplicate_sha_groups": sum(len(files) > 1 for files in labels.values()),
            "input_prediction_records": input_count,
            "additional_prediction_records_for_sha": duplicate_prediction_records,
            "conflicting_prediction_sha_groups": conflicts,
            "unique_verdict_confusion": dict(unique_counts),
            "sample_verdict_confusion": dict(sample_counts),
            "finding_reason_counts": {key: reasons[key] for key in sorted(REASON_STATUSES)},
            "human_annotated_sha_groups": covered,
            "missing_human_annotation_sha_groups": len(labels) - covered,
            "timed_human_events_available": sum(
                event.get("interval_sec") is not None
                for assertion in observed.values()
                for event in assertion.get("events", [])
            ),
            "unknown_cause_sha_groups": sum(
                bool(a.get("cause_unresolved")) for a in observed.values()
            ),
            "compatible_event_timing": {
                "with_human_time": sum(
                    t["human_interval_sec"] is not None for t in compatible_timings
                ),
                "human_time_unknown": sum(
                    t["human_interval_sec"] is None for t in compatible_timings
                ),
                "distances_to_human_interval_sec": [
                    t["absolute_distance_to_interval_sec"]
                    for t in compatible_timings
                    if t["absolute_distance_to_interval_sec"] is not None
                ],
            },
            "invalid_output_records": sum("record" in error for error in errors),
            "invalid_output_errors": len(errors),
            "unlabelled_prediction_records": len(unlabelled),
            "runtime": {
                "measured_records": len(runtimes),
                "missing_records": sum(
                    p["runtime_s"] is None for ps in predictions.values() for p in ps
                ),
                "min_sec": min(runtimes) if runtimes else None,
                "median_sec": statistics.median(runtimes) if runtimes else None,
                "max_sec": max(runtimes) if runtimes else None,
                "over_300_sec": sum(t > 300 for t in runtimes),
                "provenance": "Supplied wall/runtime fields only; no inference timed by audit.",
            },
        },
        "assertion_provenance": assertions["provenance"],
        "limitations": assertions.get("limitations", [])
        + [
            "Organizer verdicts/timestamps do not establish the reason or its legal validity.",
            "No overall reason accuracy: human coverage is partial and causes can be unknown.",
            "Per-file offsets never give timing credit to incompatible/unknown reasons.",
            "API images, full API schema, and legal citations are not validated by this audit.",
        ],
        "rule_assumptions": assertions.get("rule_assumptions", []),
        "capability_gaps": assertions.get("capability_gaps", []),
        "invalid_outputs": errors,
        "unlabelled_predictions": unlabelled,
        "clips": clips,
    }


def run_manifest(manifest_path: Path, root: Path = ROOT) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    if not isinstance(manifest.get("predictions"), list) or not manifest["predictions"]:
        raise ValueError("manifest must explicitly pin prediction files")
    # Read and hash the same bytes before parsing; fail closed if any pin changed.
    labels = read_pinned(manifest["labels"], root)
    assertions = json.loads(read_pinned(manifest["assertions"], root))
    predictions = [(entry, read_pinned(entry, root)) for entry in manifest["predictions"]]
    for entry in manifest.get("references", []):
        read_pinned(entry, root)
    report = audit(labels, predictions, assertions)
    report["inputs"] = manifest
    report["manifest_sha256"] = sha256_file(manifest_path)
    report["auditor_sha256"] = sha256_file(Path(__file__))
    return report


def markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# Independent findings audit",
        "",
        f"Organizer files: {summary['organizer_samples']}; unique SHA groups: "
        f"{summary['unique_sha_groups']}; duplicate samples: {summary['duplicate_samples']}.",
        "",
        "Verdict confusion (SHA groups): `"
        + json.dumps(summary["unique_verdict_confusion"])
        + "`.",
        "",
        "Reason statuses count findings, not organizer reason ground truth: `"
        + json.dumps(summary["finding_reason_counts"])
        + "`.",
        "",
        "Compatible human event timing: `" + json.dumps(summary["compatible_event_timing"]) + "`.",
        "",
        f"Human observations cover {summary['human_annotated_sha_groups']} SHA groups; "
        f"{summary['missing_human_annotation_sha_groups']} have no supplied event assertions.",
        "",
        "Runtime (reported records only): `" + json.dumps(summary["runtime"]) + "`.",
        "",
        f"Invalid records: {summary['invalid_output_records']}; conflicting SHA groups: "
        f"{summary['conflicting_prediction_sha_groups']}; unlabelled predictions: "
        f"{summary['unlabelled_prediction_records']}.",
        "",
        "| Files | Binary | Findings and observed reason status |",
        "|---|---|---|",
    ]
    for clip in report["clips"]:
        findings = (
            "; ".join(
                f"{f['rule_id']}@{f['t']}: **{f['reason_status']}**" for f in clip["findings"]
            )
            or "none"
        )
        lines.append(f"| {', '.join(clip['clip_ids'])} | {clip['unique_outcome']} | {findings} |")
    lines.extend(["", "## Contradicted reasons", ""])
    for clip in report["clips"]:
        for finding in clip["findings"]:
            if finding["reason_status"] == "contradicted":
                lines.append(
                    f"- {', '.join(clip['clip_ids'])}: {finding['rule_id']}@{finding['t']}. "
                    + finding["explanation"]
                )
    lines.extend(["", "## Compatible events and timing", ""])
    for clip in report["clips"]:
        for finding in clip["findings"]:
            for timing in finding["compatible_event_timing"]:
                human_time = timing["human_interval_sec"]
                delta = timing["absolute_distance_to_interval_sec"]
                lines.append(
                    f"- {', '.join(clip['clip_ids'])}, {finding['rule_id']}@{finding['t']}: "
                    f"{timing['event_id']}; human interval "
                    f"{human_time if human_time is not None else 'unknown'}; "
                    f"distance {str(delta) + ' s' if delta is not None else 'unmeasured'}."
                )
    lines.extend(["", "## Duplicate markers and annotation limits", ""])
    for clip in report["clips"]:
        if len(clip["organizer_files"]) > 1:
            markers = "; ".join(
                f"{f['clip_id']} {f['verdict']} {f['timestamps_sec']} s"
                for f in clip["organizer_files"]
            )
            lines.append(f"- Same SHA: {markers}. These markers do not identify the reason.")
        observed = clip["human_observation"] or {}
        for event in observed.get("events", []):
            if event.get("interval_sec") is not None:
                lines.append(
                    f"- Human event {', '.join(clip['clip_ids'])}, {event['id']}: "
                    f"{event['interval_sec']} s; only a compatible reason can use this timing."
                )
        if observed.get("cause_unresolved"):
            lines.append(f"- {', '.join(clip['clip_ids'])}: cause unresolved; no reason score.")
        if observed.get("recording_cutoff"):
            lines.append(
                f"- {', '.join(clip['clip_ids'])}: recording cutoff; future abandonment unobserved."
            )
    lines.extend(["", "## Prioritized source-review assumptions", ""])
    for assumption in report["rule_assumptions"]:
        lines.append(f"- {assumption['priority']} {assumption['id']}: {assumption['question']}")
    lines.extend(["", "## Capability gaps", ""])
    for gap in report["capability_gaps"]:
        lines.append(f"- {gap['id']}: {gap['explanation']}")
    lines.extend(["", "## Limits and provenance", ""])
    lines.extend(["Assertions: `" + report["assertion_provenance"]["id"] + "`.", ""])
    lines.extend("- " + limitation for limitation in report["limitations"])
    lines.extend(["", "Exact input paths and hashes are in the JSON report's `inputs` field.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pin = commands.add_parser("pin", help="freeze explicit text input paths/hashes")
    pin.add_argument("--labels", type=Path, required=True)
    pin.add_argument("--predictions", type=Path, action="append", required=True)
    pin.add_argument("--assertions", type=Path, required=True)
    pin.add_argument("--reference", type=Path, action="append", default=[])
    pin.add_argument("--clip", help="explicit identity for a single full API result")
    pin.add_argument("--root", type=Path, default=ROOT)
    pin.add_argument("--out", type=Path, required=True)
    run = commands.add_parser("run", help="verify all pins and write an independent audit")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--root", type=Path, default=ROOT)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "pin":
            manifest = make_manifest(
                args.labels, args.predictions, args.assertions, args.root.resolve()
            )
            manifest["references"] = [pin_file(p, args.root.resolve()) for p in args.reference]
            if args.clip:
                if len(args.predictions) != 1:
                    raise ValueError("--clip requires exactly one prediction input")
                manifest["predictions"][0]["clip_id"] = parse_clip_id(args.clip)
            dump_json(args.out, manifest)
        else:
            report = run_manifest(args.manifest, args.root.resolve())
            dump_json(args.out, report)
            if args.markdown:
                args.markdown.parent.mkdir(parents=True, exist_ok=True)
                args.markdown.write_text(markdown(report), encoding="utf-8")
            print(json.dumps(report["summary"], sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Never print external exception payloads, which can include image strings/secrets.
        print(
            f"audit failed ({type(exc).__name__}); check input paths, schema and SHA pins",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
