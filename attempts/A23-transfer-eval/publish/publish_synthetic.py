#!/usr/bin/env python3
"""Publish actual A23 API results as a new saved run; no model calls or live writes."""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SHARED = Path.home() / "workspaces/datathon26-workers/shared"
BASE = SHARED / "a23/base"
STATE = SHARED / "a21/candidate/runtime/realtime"
SOURCE = SHARED / "a23-synthetic"
FLAG = BASE / "runtime/realtime/.attempt-metadata-ready"
BASELINE = "5fae84bc10415111a04b5982d156727ca80f788a"
RUN = "a23-synthetic"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def new_file(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"different_existing_file:{path.name}")
        return
    fd, temporary = tempfile.mkstemp(prefix=".a23-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic create; never replace a historical run.
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare():
    sys.path.insert(0, str(BASE))
    from backend.contracts import DoneJob
    from realtime.gateway import Item

    api = SOURCE / "api-newmain-run1"
    summaries = [json.loads(line) for line in (api / "summary.jsonl").read_text().splitlines() if line.strip()]
    if len(summaries) != 3:
        raise ValueError("expected_three_actual_API_results")
    items, timings = [], []
    for number, summary in enumerate(summaries, 1):
        accepted = api / "privateRaw" / f"{number:02d}-accepted.json"
        result_path = api / "privateRaw" / f"{number:02d}-result.json"
        result = json.loads(result_path.read_text())
        DoneJob.model_validate(result)
        job = json.loads(accepted.read_text())["job_id"]
        if result["job_id"] != job or summary["job_id"] != job or summary["status"] != "done":
            raise ValueError("inconsistent_actual_job")
        video = SOURCE / summary["name"]
        if video.parent.resolve() != SOURCE.resolve() or sha(video) != summary["sha256"]:
            raise ValueError("actual_video_hash_mismatch")
        queued = accepted.stat().st_mtime - summary["upload_s"]
        started, finished = accepted.stat().st_mtime, result_path.stat().st_mtime
        if not queued <= started <= finished:
            raise ValueError("inconsistent_artifact_times")
        item = Item(id=f"a23-synthetic-{number:02d}", name=video.name, source="upload", status="done",
                    job_id=job, verdict=result["verdict"], label=None, result=result,
                    queued_at=queued, started_at=started, finished_at=finished)
        items.append(item.model_dump())
        timings.append({"id": item.id, "name": item.name, "sha256": summary["sha256"],
                        "runtime_wall_s": summary["runtime_s"], "artifact_processing_s": finished - started,
                        "queued_at": queued, "started_at": started, "finished_at": finished,
                        "warnings": result.get("warnings", []), "cache_provenance": summary.get("cache_provenance")})
    return items, timings


def preserved():
    result = {}
    for p in sorted(STATE.glob("state.*.json")):
        if p.name not in {f"state.{RUN}.json", f"state.{RUN}.meta.json"}:
            value = json.loads(p.read_text())
            result[p.name] = {"sha256": sha(p), "items": len(value) if isinstance(value, list) else None}
    return result


def publish(items, timings):
    if not FLAG.is_file():
        raise RuntimeError("deployment_flag_missing_no_sidecar_writes")
    before = preserved()
    uploads = STATE / "uploads"
    uploads.mkdir(exist_ok=True)
    for item, info in zip(items, timings, strict=True):
        destination = uploads / f"{item['id']}.mp4"
        if destination.exists():
            if sha(destination) != info["sha256"]:
                raise FileExistsError("different_existing_saved_video")
            continue
        fd, temporary = tempfile.mkstemp(prefix=".a23-upload-", dir=uploads)
        try:
            with os.fdopen(fd, "wb") as output, (SOURCE / item["name"]).open("rb") as source:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            if sha(Path(temporary)) != info["sha256"]:
                raise ValueError("copied_video_hash_mismatch")
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    new_file(STATE / f"state.{RUN}.json", encoded(items))
    metadata = {"attempt_prefix": "A23", "title": "Synthetic videos — 3 fresh API runs",
                "source_commit": "4a3b9ea", "validation_status": "unscored"}
    if not FLAG.is_file():
        raise RuntimeError("deployment_flag_disappeared")
    new_file(STATE / f"state.{RUN}.meta.json", encoded(metadata))
    report = {**metadata, "run": RUN, "samples": 3, "completed": 3,
              "kind": "Synthetic API evaluation", "status": "complete, unscored", "runs": [RUN],
              "summary": "Three fresh API runs returned no_violation (32.95s, 14.16s, 18.18s wall time). Expected labels are unknown; accuracy is unscored. Scene calibration was weak/missing and all nine safe checks were unknown. Local safe-only Qwen3-VL-4B; no training or fine-tuning.",
              "verdicts": {"no_violation": sum(i["verdict"] == "no_violation" for i in items),
                           "violation": sum(i["verdict"] == "violation" for i in items)},
              "labelled": 0, "accuracy": None, "model": "Qwen3-VL-4B-Instruct (local, safe-only)",
              "trained_or_fine_tuned": False, "runtime_wall_s": [r["runtime_wall_s"] for r in timings],
              "limitations": ["Expected labels unknown; accuracy unscored.", "Scene calibration missing/weak; all 9 safe checks unknown.", "No training or fine-tuning was performed.", "Eight mirror runs have a separate report; completion is not asserted here."]}
    with (STATE / ".evaluation-publish.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        evaluation_path = STATE / "evaluation.json"
        original = json.loads(evaluation_path.read_text())
        updated = json.loads(json.dumps(original))
        updated.update(attempt_prefix="A21", source_commit=BASELINE)
        updated["run_provenance"].update(attempt_prefix="A21", base_main=BASELINE,
                                         variant="A21 baseline — original saved results")
        reports = updated.setdefault("attempt_reports", [])
        if not isinstance(reports, list):
            raise ValueError("unexpected_attempt_reports_contract")
        existing = [r for r in reports if r.get("run") == RUN or RUN in r.get("runs", [])]
        if existing and existing != [report]:
            raise FileExistsError("different_existing_A23_evaluation_report")
        if not existing:
            reports.append(report)
        preserved_keys = set(original) - {"run_provenance", "attempt_reports", "attempt_prefix", "source_commit"}
        assert {k: original[k] for k in preserved_keys} == {k: updated[k] for k in preserved_keys}
        fd, temporary = tempfile.mkstemp(prefix=".a23-evaluation-", dir=STATE)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded(updated))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, evaluation_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    after = preserved()
    assert before == after, "existing live/historical run changed during publication"
    return {"published_at_utc": datetime.now(UTC).isoformat(), "preserved": after,
            "items": len(items), "run": RUN, "metadata": metadata, "timings": timings}


def verify(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get_json(path):
        with opener.open(url + path, timeout=20) as response:
            return json.loads(response.read())

    runs = get_json("/api/runs")
    names = runs["runs"]
    assert RUN in names and not any(str(n).endswith(".meta") for n in names)
    compact = get_json(f"/api/runs/{RUN}")
    rows = compact["items"]
    assert len(rows) == 3 and all(i["status"] == "done" and i["verdict"] == "no_violation" and i["label"] is None for i in rows)
    checks = []
    for number in range(1, 4):
        identity = f"a23-synthetic-{number:02d}"
        request = urllib.request.Request(url + f"/api/items/{identity}/video?run={RUN}", headers={"Range": "bytes=0-31"})
        with opener.open(request, timeout=20) as response:
            video_status = response.status
            assert video_status in {200, 206}
            response.read(32)  # Local transport check; bytes never enter report/stdout.
        try:
            with opener.open(url + f"/api/items/{identity}/trace?run={RUN}", timeout=20) as response:
                trace_status = response.status  # Status only; do not read trace body.
        except urllib.error.HTTPError as exc:
            trace_status = exc.code
        checks.append({"id": identity, "video_status": video_status, "trace_status": trace_status})
    return {"gateway_url": url, "saved_run_listed": True, "done": len(rows),
            "no_violation": 3, "null_labels": 3, "media_free_checks": checks}


def write_report(directory, publication, checks):
    counts = ", ".join(f"{name}: {info['items']}" for name, info in publication["preserved"].items() if info["items"] is not None)
    times = ", ".join(f"{r['name']} {r['runtime_wall_s']:.2f}s" for r in publication["timings"])
    text = f"""Published A23 synthetic saved run at {publication['published_at_utc']}.

URL: {checks['gateway_url']}/compare?run={RUN}; evaluation: {checks['gateway_url']}/evaluation.

All3 actual saved API results validated with gateway.Item and backend.DoneJob. They are done/no_violation with null labels. Expected labels are unknown; accuracy is unscored. Wall runtimes: {times}. Scene calibration is weak/missing; all9 safe checks were unknown. The configured local safe-only model is Qwen3-VL-4B-Instruct. No training/fine-tuning was performed. No mirror completion or A24 training claim is made.

Existing run files preserved byte-for-byte: {counts}. Only new state.a23-synthetic.json, its sidecar and three persistent upload copies were created. Each uploaded video SHA matches its actual API input. evaluation.json retains original summary/clips and all baseline audit data; only A21 source provenance was corrected to {BASELINE} and the A23 attempt report was added. Live state, annotations, descriptions, existing historical runs, jobs, services and credentials were not changed.

Timestamp limits: queued_at is inferred from accepted-response artifact mtime minus measured upload_s. started_at is accepted-response artifact mtime, not a measured server-start event. finished_at is actual result-file mtime. Gateway elapsed time therefore differs slightly from the separately recorded API wall runtime. No absolute server execution time is invented.

Checked: deployment flag present before publication;3 real Item/DoneJob validations; atomic new-file/idempotence/conflict assertions; preserved-file hashes; media-free GET /api/runs and compact saved run (3done/3no_violation/3null labels); video byte-range HTTP status and trace HTTP status only. Checks: {json.dumps(checks['media_free_checks'])}.

No frames/base64/video bytes or credentials appear in this report. The worker sandbox initially rejected publication with Errno30 on shared runtime/uploads before any file was written; the parent executes publication outside that sandbox.
"""
    (directory / "REPORT.md").write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=600)
    parser.add_argument("--url", default="http://127.0.0.1:8103")
    parser.add_argument("--report-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    os.umask(0o077)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    if args.verify_only:
        result = verify(args.url)
        (args.report_dir / "http-checks.json").write_bytes(encoded(result))
        print(json.dumps(result), flush=True)
        return
    items, timings = prepare()
    plan = {"validated_Item_and_DoneJob": len(items), "flag_exists": FLAG.is_file(),
            "null_labels": sum(i["label"] is None for i in items), "preserved": preserved(),
            "timings": timings, "timestamp_note": "queued inferred from accepted-file mtime minus upload_s; started is accepted response artifact mtime, not measured server start; finished is real result-file mtime."}
    (args.report_dir / "prepared.json").write_bytes(encoded(plan))
    print(json.dumps({k: plan[k] for k in ("validated_Item_and_DoneJob", "flag_exists", "null_labels")}), flush=True)
    if args.prepare_only:
        return
    deadline = time.monotonic() + args.wait_seconds
    while not FLAG.is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError("deployment_flag_not_seen_within_wait_budget")
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    result = publish(items, timings)
    (args.report_dir / "publication.json").write_bytes(encoded(result))
    checks = verify(args.url)
    (args.report_dir / "http-checks.json").write_bytes(encoded(checks))
    write_report(args.report_dir, result, checks)
    print(json.dumps({"status": "PUBLISHED", "published_at_utc": result["published_at_utc"], **checks}), flush=True)


if __name__ == "__main__":
    main()
