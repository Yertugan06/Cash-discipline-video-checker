import ipaddress
import json
import os
import secrets
import time
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from backend.codex import Codex, load_codex
from backend.config import Settings
from backend.evaluation import group_videos, read_labels, score
from backend.models import AnalysisResult
from backend.pipeline import analyze_video


def write_progress(out: Path, total: int, rows: list[dict], current: list[str] | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "done" if len(rows) == total else "processing",
        "total": total,
        "completed": len(rows),
        "failed": sum(row["status"] == "failed" for row in rows),
        "current": current,
        "last_video": rows[-1]["aliases"] if rows else None,
        "last_runtime_sec": rows[-1]["end_to_end_sec"] if rows else None,
        "updated_at": time.time(),
        "videos": [
            {
                "aliases": row["aliases"],
                "status": row["status"],
                "error": row.get("error"),
                "labels": row.get("labels", []),
                "runtime_sec": row["end_to_end_sec"],
                "verdict": (row.get("result") or {}).get("verdict"),
                "violations": [
                    {key: violation[key] for key in ("rule_id", "timecode_sec", "type")}
                    for violation in (row.get("result") or {}).get("violations", [])
                ],
                "debug_path": row.get("debug_path"),
            }
            for row in rows
        ],
    }
    temporary = out / "progress.json.partial"
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(out / "progress.json")


def validate_local_url(url: str) -> str:
    parsed = urlsplit(url)
    try:
        loopback = (
            parsed.hostname == "localhost"
            or ipaddress.ip_address(parsed.hostname or "").is_loopback
        )
    except ValueError:
        loopback = False
    if (
        not loopback
        or parsed.scheme not in {"http", "https"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("--api-url must be a loopback HTTP(S) origin; videos must stay local")
    return url.rstrip("/")


def validate_sources(result: AnalysisResult, codex: Codex) -> None:
    rules = {rule.id: rule for rule in codex.rules}
    for violation in result.violations:
        rule = rules.get(violation.rule_id)
        if rule is None or (violation.source, violation.source_url, violation.strength) != (
            rule.source,
            rule.source_url,
            rule.strength,
        ):
            raise ValueError("Prediction cites a rule/source absent from codex.yaml")


def analyze_via_api(
    video: Path, output: Path, *, api_url: str, api_key: str, timeout_sec: float, debug: bool
) -> AnalysisResult:
    origin = validate_local_url(api_url)
    if not api_key:
        raise ValueError("API_KEY must be set for --via-api")
    deadline = time.perf_counter() + timeout_sec

    def remaining() -> float:
        seconds = deadline - time.perf_counter()
        if seconds <= 0:
            raise TimeoutError("API job exceeded the end-to-end time limit")
        return seconds

    with httpx.Client(base_url=origin, headers={"X-API-Key": api_key}, trust_env=False) as client:
        with video.open("rb") as stream:
            response = client.post(
                "/api/v1/analyze",
                params={"debug": str(debug).lower()},
                files={"file": (video.name, stream, "video/quicktime")},
                timeout=remaining(),
            )
        response.raise_for_status()
        job_id = response.json()["job_id"]
        while True:
            response = client.get(f"/api/v1/jobs/{job_id}", timeout=remaining())
            response.raise_for_status()
            payload = response.json()
            if payload["status"] == "failed":
                raise RuntimeError(f"API processing failed: {payload['error']}")
            if payload["status"] == "done":
                result = AnalysisResult.model_validate(payload)
                if debug:
                    response = client.get(f"/api/v1/jobs/{job_id}/debug", timeout=remaining())
                    response.raise_for_status()
                    output.mkdir(parents=True, exist_ok=True)
                    (output / "debug.mp4").write_bytes(response.content)
                return result
            if payload["status"] != "processing":
                raise ValueError(f"Unknown API job status: {payload['status']}")
            time.sleep(min(0.25, remaining()))


def evaluate(
    videos: Path,
    labels: Path,
    out: Path,
    settings: Settings,
    *,
    via_api: bool = False,
    api_url: str = "http://127.0.0.1:8000",
    debug: bool = False,
    held_out_layout: str = "Desk near the door",
) -> tuple[list[dict], list[dict]]:
    codex = load_codex(settings.codex_path)
    groups = group_videos(videos, read_labels(labels), codex)
    if not any(held_out_layout in group.layouts for group in groups):
        raise ValueError(
            f"Held-out camera layout absent from codex clip mappings: {held_out_layout}"
        )
    if via_api:
        validate_local_url(api_url)
        if not os.environ.get("API_KEY"):
            raise ValueError("API_KEY must be set for --via-api")
    rows = []
    run_dir = out / "runs" / uuid4().hex[:12]
    config = replace(settings, work_dir=run_dir)
    for group in groups:
        write_progress(out, len(groups), rows, group.aliases)
        output = run_dir / group.checksum[:16]
        row = {
            "aliases": group.aliases,
            "file": group.path.name,
            "checksum": group.checksum,
            "labels": [asdict(event) for event in group.labels],
            "layouts": sorted(group.layouts),
            "split": "held_out" if held_out_layout in group.layouts else "training",
            "status": "done",
            "error": None,
            "result": None,
            "debug_path": None,
        }
        started = time.perf_counter()
        try:
            result = (
                analyze_via_api(
                    group.path,
                    output,
                    api_url=api_url,
                    api_key=os.environ["API_KEY"],
                    timeout_sec=settings.timeout_sec,
                    debug=debug,
                )
                if via_api
                else analyze_video(group.path, output, config, debug=debug)
            )
            validate_sources(result, codex)
            if any(event.timestamp_sec > result.video.duration_sec for event in group.labels):
                raise ValueError("A labelled timestamp exceeds the decoded video duration")
            row["result"] = result.model_dump()
            output.mkdir(parents=True, exist_ok=True)
            (output / "analysis.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8"
            )
            if debug:
                row["debug_path"] = (output / "debug.mp4").relative_to(out).as_posix()
        except Exception as exc:
            # Every failure stays in the denominator and in the report; it is never a clean result.
            row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        row["end_to_end_sec"] = time.perf_counter() - started
        rows.append(row)
        write_progress(out, len(groups), rows, None)
        print(
            f"{'/'.join(group.aliases)}: {row['status']} ({row['end_to_end_sec']:.2f} s)",
            flush=True,
        )
    summaries = [
        score(rows, codex, "all_unique"),
        score(rows, codex, "all_clips", weight_aliases=True),
        score([row for row in rows if row["split"] == "held_out"], codex, "held_out"),
        score([row for row in rows if row["split"] == "training"], codex, "training"),
    ]
    return rows, summaries


def evaluation_settings(codex_path: Path, sample_fps: float, **options) -> Settings:
    # Direct evaluation does not authenticate; this generated key is never served or stored.
    return Settings(
        api_key=secrets.token_urlsafe(32), codex_path=codex_path, sample_fps=sample_fps, **options
    )
