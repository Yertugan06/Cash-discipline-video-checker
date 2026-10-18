#!/usr/bin/env python3
"""Sequential localhost checker evaluation; export only allowlisted text/numbers."""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# Unknown keys are dropped at EVERY depth, including model-generated fields.
EXPORT_FIELDS = frozenset("""name sha256 job_id status api_status verdict error error_type http_status runtime_s
upload_s processing_s trace_s findings violations rule_id t timecode_sec type description
source source_url source_quote strength citation_status jurisdiction document_title
issuing_authority act_number adopted_on detection_confidence business_status
implementation_status warnings coverage step_s planned done failed deadline_hit mode
video_sha256 perception_cache_hit fps duration_sec scene objects zones cashier_direction
cashier_position confidence candidates label score box track_id role body hands
desk laptop safe door counter cashier client roles cash state_changes key value margin events
timestamp_sec facts actor_id observed_entry confirmed_exit previous_actor_id client_id
client_ids session_id start end cash_ids counted_cash_ids cash_id location previous_location
counted bag_open_seen kind condition_id duration_sec end_reason object track_ids owner
window_end visit_start_sec bag_appeared_sec last_bag_area_reach_sec away_s held_sec
frames dets visual_checks family answer ok question_id trigger trigger_t observed_entry
cache_hit cache_key attempts requested_t source_track_ids support_t state_source state_t
kept timestamp_sec boxes desk_objects_enabled desk_objects config_sha256 model_sha256
cache_provenance visual_checks_count visual_cache_hits source_pins source_commit
manifest_sha256 runner_sha256 files path server_source_commit input_count
fresh_perception_required trace_status model input_sha256 before after sec enabled
""".split())
MEDIA_TEXT = re.compile(r"data:[^\s,]*[;,]|base64|/9j/|iVBORw0KGgo|[A-Za-z0-9+/=]{128,}", re.I)


def safe_export(value, secret=""):
    if isinstance(value, dict):
        return {k: safe_export(v, secret) for k, v in value.items() if k in EXPORT_FIELDS}
    if isinstance(value, list):
        return [safe_export(v, secret) for v in value]
    if isinstance(value, str):
        if len(value) > 8000 or MEDIA_TEXT.search(value) or (secret and secret in value):
            return "[omitted]"
        return value
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


class ClientError(RuntimeError):
    """Fixed client error code, safe to export without response/header text."""


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha_file(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def load_inputs(manifest, videos):
    payload = json.loads(manifest.read_text())
    rows = payload["inputs"] if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ClientError("empty_or_invalid_manifest")
    result = []
    seen = set()
    for row in rows:
        name, expected = row["file"], row["sha256"]
        if not isinstance(name, str) or not name.isprintable() or Path(name).name != name or name in seen:
            raise ClientError("invalid_or_duplicate_input_name")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ClientError("invalid_sha256")
        video = (videos / name).resolve()
        if video.parent != videos.resolve() or not video.is_file():
            raise ClientError("input_missing_or_outside_video_directory")
        if sha_file(video) != expected:
            raise ClientError("input_sha256_mismatch")
        seen.add(name)
        result.append((video, expected))
    commit = payload.get("source_commit") if isinstance(payload, dict) else None
    return result, commit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def self_check():
    dirty = {"name": "t1.mp4", "job_id": "a" * 32, "image_base64": "FORBIDDEN_MEDIA", "frames": [
        {"t": 1.5, "jpeg": "FORBIDDEN_MEDIA", "facts": {"actor_id": "person:1", "image_base64": "FORBIDDEN_MEDIA"}}],
        "violations": [{"rule_id": "L-PC-LOCKED", "description": "Readable explanation", "source_quote": "data:image/jpeg;base64,FORBIDDEN_MEDIA"}],
        "error": "private-test-key", "unexpected": {"rule_id": "FORBIDDEN_MEDIA"}}
    cleaned = safe_export(dirty, "private-test-key")
    text = json.dumps(cleaned)
    assert cleaned["name"] == "t1.mp4"
    assert "FORBIDDEN_MEDIA" not in text and "private-test-key" not in text
    assert "image_base64" not in text and "jpeg" not in text
    assert cleaned["frames"][0] == {"t": 1.5, "facts": {"actor_id": "person:1"}}
    assert cleaned["violations"][0]["description"] == "Readable explanation"
    assert cleaned["violations"][0]["source_quote"] == "[omitted]"
    assert safe_export({"description": "/9j/" + "a" * 200}) == {"description": "[omitted]"}
    print("export assertions passed: recursive media/key removal, text retained")


def run(args):
    url = urllib.parse.urlsplit(args.url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ClientError("only_localhost_http_origin_allowed")
    if args.job_timeout <= 270 or args.upload_timeout <= 0:
        raise ClientError("job_timeout_must_exceed_270_seconds")
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    raw = args.out / "privateRaw"
    raw.mkdir(mode=0o700)
    key = args.key_file.read_text().strip()
    if not key or "\n" in key or "\r" in key:
        raise ClientError("invalid_key_file")
    inputs, commit = load_inputs(args.inputs, args.videos)
    pins = {"source_commit": commit, "manifest_sha256": sha_file(args.inputs), "runner_sha256": sha_file(Path(__file__)), "server_source_commit": "not_exposed_by_API", "files": []}
    for relative in ("backend/main.py", "backend/contracts.py", "backend/f1/detector.py", "backend/f1/perception.py", "backend/f1/events.py", "backend/f1/rules.py", "config/perception.yaml", "knowledge/rules.yaml"):
        source = args.source_dir / relative
        if not source.is_file():
            raise ClientError("source_pin_file_missing")
        pins["files"].append({"path": relative, "sha256": sha_file(source)})
    write_json(args.out / "source-pins.json", safe_export({"source_pins": pins, "input_count": len(inputs), "fresh_perception_required": True}, key))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(method, path, timeout, body=None, content_type=None):
        request = urllib.request.Request(args.url.rstrip("/") + path, data=body, method=method, headers={"X-API-Key": key})
        if content_type:
            request.add_header("Content-Type", content_type)
        with opener.open(request, timeout=max(0.1, timeout)) as response:
            return response.status, response.read()

    errors = 0
    for position, (video, expected) in enumerate(inputs, 1):
        started = time.monotonic()
        row = {"name": video.name, "sha256": expected, "status": "error", "coverage": None, "cache_provenance": None}
        terminal = False
        stage = "upload"
        display_name = safe_export(video.name, key)
        print(f"[{position}/{len(inputs)}] {display_name}: uploading", flush=True)
        try:
            data = video.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ClientError("input_changed_before_upload")
            boundary = uuid.uuid4().hex
            # Only the verified video is submitted; manifest labels never enter the request.
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input{video.suffix.lower()}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + f"\r\n--{boundary}--\r\n".encode())
            code, response = call("POST", "/api/v1/analyze", args.upload_timeout, body, f"multipart/form-data; boundary={boundary}")
            (raw / f"{position:02d}-accepted.json").write_bytes(response)
            if code != 202:
                raise ClientError("unexpected_upload_status")
            accepted = json.loads(response)
            job_id = accepted.get("job_id")
            if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
                raise ClientError("invalid_job_id")
            row.update(job_id=job_id, upload_s=time.monotonic() - started)
            deadline = time.monotonic() + args.job_timeout
            stage = "poll"
            next_progress = time.monotonic() + 30
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("job_deadline")
                code, response = call("GET", f"/api/v1/jobs/{job_id}", min(30, remaining))
                (raw / f"{position:02d}-result.json").write_bytes(response)
                result = json.loads(response)
                if code != 200 or result.get("job_id") != job_id:
                    raise ClientError("invalid_poll_response")
                status = result.get("status")
                if status in {"done", "failed"}:
                    terminal = True
                    break
                if status != "processing":
                    raise ClientError("unexpected_job_state")
                if time.monotonic() >= next_progress:
                    print(f"[{position}/{len(inputs)}] {display_name}: processing ({time.monotonic() - started:.1f}s)", flush=True)
                    next_progress = time.monotonic() + 30
                time.sleep(min(1, max(0, deadline - time.monotonic())))
            row.update(api_status=status, processing_s=time.monotonic() - started - row["upload_s"])
            if status == "failed":
                row.update(status="failed", error=result.get("error", "checker_failed"))
            else:
                if result.get("verdict") not in {"violation", "no_violation"} or not isinstance(result.get("violations"), list):
                    raise ClientError("invalid_done_contract")
                row.update(status="done", verdict=result["verdict"], violations=result["violations"], warnings=result.get("warnings", []), coverage=result.get("coverage"))
            stage = "trace"
            trace_started = time.monotonic()
            try:
                code, trace_data = call("GET", f"/api/v1/jobs/{job_id}/trace", 30)
            except urllib.error.HTTPError as exc:
                if status == "failed" and exc.code == 404:
                    row["trace_status"] = "not_available_for_failed_job"
                    trace_data = None
                else:
                    raise
            if trace_data is not None:
                (raw / f"{position:02d}-trace.json").write_bytes(trace_data)
                trace = json.loads(trace_data)
                write_json(args.out / f"{position:02d}-numeric-trace.json", safe_export(trace, key))
                row["cache_provenance"] = {"video_sha256": trace.get("video_sha256"), "perception_cache_hit": trace.get("perception_cache_hit"), "visual_checks_count": len(trace.get("visual_checks", [])), "visual_cache_hits": sum(c.get("cache_hit") is True for c in trace.get("visual_checks", []))}
                if status == "done" and (trace.get("video_sha256") != expected or trace.get("perception_cache_hit") is not False or not trace.get("frames")):
                    raise ClientError("trace_missing_fresh_matching_perception")
                row["trace_status"] = "available"
            row["trace_s"] = time.monotonic() - trace_started
        except Exception as exc:
            row.update(status="error", error_type=type(exc).__name__, error=str(exc) if isinstance(exc, ClientError) else f"{stage}_error")
            if isinstance(exc, urllib.error.HTTPError):
                row["http_status"] = exc.code
                (raw / f"{position:02d}-http-error.body").write_bytes(exc.read())
        numeric_path = args.out / f"{position:02d}-numeric-trace.json"
        if row.get("job_id") and not numeric_path.exists():
            write_json(numeric_path, safe_export({"job_id": row["job_id"], "status": "unavailable", "trace_status": row.get("trace_status", "trace_error"), "error": row.get("error")}, key))
        row["runtime_s"] = time.monotonic() - started
        exported = safe_export(row, key)
        with (args.out / "summary.jsonl").open("a") as stream:
            stream.write(json.dumps(exported, ensure_ascii=False, allow_nan=False) + "\n")
        print(f"[{position}/{len(inputs)}] {display_name}: {row['status']} ({row['runtime_s']:.2f}s)", flush=True)
        errors += row["status"] != "done"
        if not terminal:
            print("Stopped: no confirmed terminal job; no further upload queued.", flush=True)
            break
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--videos", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    parser.add_argument("--source-dir", type=Path, default=Path.home() / "workspaces/datathon26-workers/shared/a23/base")
    parser.add_argument("--job-timeout", type=float, default=360)
    parser.add_argument("--upload-timeout", type=float, default=120)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    if any(getattr(args, k) is None for k in ("inputs", "videos", "key_file", "out")):
        parser.error("--inputs --videos --key-file --out are required")
    try:
        return run(args)
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "error": str(exc) if isinstance(exc, ClientError) else "client_setup_error"}), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
