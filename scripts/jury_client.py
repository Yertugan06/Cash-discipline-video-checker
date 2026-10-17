#!/usr/bin/env python3
"""Reference client for the jury API (task.md §10): upload one .mov, poll
for the result, validate it against `backend.contracts.DoneJob`, and print a
short summary. Meant to run from a laptop outside the VM -- it only talks to
the public URL over HTTP(S); it never touches the server's filesystem.

Usage:
    API_KEY=... python scripts/jury_client.py https://team.example.kz video_017.mov
    python scripts/jury_client.py https://team.example.kz video_017.mov --api-key ...
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.contracts import DoneJob, FailedJob, ProcessingJob  # noqa: E402

DEFAULT_TIMEOUT_S = 300.0  # task.md FAQ C.14: "Есть ли лимит времени... 5 минут."
DEFAULT_POLL_INTERVAL_S = 2.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Public service URL, e.g. https://team.example.kz")
    parser.add_argument("video", type=Path, help="Path to a local .mov file")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY"),
        help="X-API-Key value; defaults to the API_KEY environment variable",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_S)
    args = parser.parse_args(argv)
    if not args.api_key:
        parser.error("No API key: pass --api-key or set the API_KEY environment variable")
    if not args.video.is_file():
        parser.error(f"No such file: {args.video}")
    return args


def submit(client: httpx.Client, video: Path) -> str:
    with video.open("rb") as handle:
        response = client.post(
            "/api/v1/analyze", files={"file": (video.name, handle, "video/quicktime")}
        )
    if response.status_code != 202:
        raise SystemExit(f"Upload rejected: HTTP {response.status_code}: {response.text[:500]}")
    job_id = response.json()["job_id"]
    print(f"Accepted: job_id={job_id}")
    return job_id


def poll(client: httpx.Client, job_id: str, *, timeout: float, poll_interval: float) -> dict:
    started = time.monotonic()
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            raise SystemExit(f"Timed out after {elapsed:.0f}s waiting for job {job_id}")
        response = client.get(f"/api/v1/jobs/{job_id}")
        if response.status_code != 200:
            raise SystemExit(
                f"GET /jobs/{job_id} -> HTTP {response.status_code}: {response.text[:500]}"
            )
        payload = response.json()
        status = payload.get("status")
        if status == "processing":
            ProcessingJob.model_validate(payload)
            time.sleep(poll_interval)
            continue
        if status == "failed":
            failed = FailedJob.model_validate(payload)
            print(f"FAILED after {elapsed:.1f}s: {failed.error}")
            return payload
        return payload


def summarize(payload: dict, elapsed_s: float) -> None:
    try:
        job = DoneJob.model_validate(payload)
    except ValidationError as exc:
        print("Result does NOT validate against backend.contracts.DoneJob:")
        print(exc)
        raise SystemExit(1) from exc
    print(f"Validated against DoneJob (jury contract) in {elapsed_s:.1f}s total.")
    print(f"verdict: {job.verdict}")
    print(f"violations: {len(job.violations)}")
    for violation in job.violations:
        frames = len(violation.evidence_frames)
        print(
            f"  - {violation.type!r} at {violation.timecode_sec:.1f}s "
            f"({frames} evidence frame{'s' if frames != 1 else ''}, "
            f"citation_status={violation.citation_status})"
        )
    if job.warnings:
        print(f"warnings: {job.warnings}")
    if job.coverage is not None:
        print(
            f"coverage: mode={job.coverage.mode} step_s={job.coverage.step_s} "
            f"done={job.coverage.done}/{job.coverage.planned} failed={job.coverage.failed}"
        )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    started = time.monotonic()
    with httpx.Client(
        base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=60.0
    ) as client:
        job_id = submit(client, args.video)
        payload = poll(client, job_id, timeout=args.timeout, poll_interval=args.poll_interval)
    elapsed = time.monotonic() - started
    if payload.get("status") != "done":
        raise SystemExit(1)
    summarize(payload, elapsed)


if __name__ == "__main__":
    main()
