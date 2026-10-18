"""External acceptance suite (implementation-plan.md WP4 "Integration tests").

Uploads every ``*.mov`` clip in ``E2E_CLIPS_DIR`` through the **public** API
(``E2E_BASE_URL`` + ``E2E_API_KEY``), polls ``/api/v1/jobs/{id}`` until it
leaves ``processing``, and checks that:

- the job reaches ``done`` in under 300 s (task.md §10: 5-minute budget);
- the response validates against the frozen ``backend.contracts.DoneJob``
  shape;
- every evidence frame's ``image_base64`` decodes as a real JPEG (Pillow);
- every violation carries the norm fields the UI's norm block needs
  (``rule_id``, ``source``, ``source_url``, ``citation_status``).

Run against a deployed service::

    E2E_BASE_URL=https://team.example.kz \\
    E2E_API_KEY=<key> \\
    E2E_CLIPS_DIR=/path/to/clips \\
    .venv/bin/python -m pytest tests/e2e

Skips with an explicit reason when any of the three env vars is unset, or
when ``E2E_CLIPS_DIR`` has no ``.mov`` files -- it never fails the suite
just because it was not configured.

Privacy: this suite never prints a clip's description, violation type text,
or norm quote -- only the clip's filename (metadata, not content), verdict,
counts and timings (SHARED_BRIEF.md privacy rule).
"""

from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from backend.contracts import DoneJob

BASE_URL = os.environ.get("E2E_BASE_URL")
API_KEY = os.environ.get("E2E_API_KEY")
CLIPS_DIR = os.environ.get("E2E_CLIPS_DIR")

JOB_BUDGET_S = 300.0  # task.md §10: "обработка видео может занимать несколько минут... 5 минут"
POLL_INTERVAL_S = 3.0
REQUEST_TIMEOUT_S = 30.0

_MISSING_ENV_REASON = (
    "set E2E_BASE_URL, E2E_API_KEY and E2E_CLIPS_DIR to run the external "
    "acceptance suite against a deployed service"
)


def _clips() -> list[Path]:
    if not CLIPS_DIR:
        return []
    root = Path(CLIPS_DIR)
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.mov") if p.is_file())


def _clip_params() -> list[pytest.param]:
    if not (BASE_URL and API_KEY and CLIPS_DIR):
        return [pytest.param(None, id="no-env", marks=pytest.mark.skip(reason=_MISSING_ENV_REASON))]
    clips = _clips()
    if not clips:
        reason = f"no .mov clips found in E2E_CLIPS_DIR={CLIPS_DIR!r}"
        return [pytest.param(None, id="no-clips", marks=pytest.mark.skip(reason=reason))]
    return [pytest.param(clip, id=clip.stem) for clip in clips]


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL or "http://unset.invalid", timeout=REQUEST_TIMEOUT_S) as c:
        yield c


def _analyze(client: httpx.Client, clip: Path) -> str:
    with clip.open("rb") as handle:
        response = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": API_KEY or ""},
            files={"file": (clip.name, handle, "video/quicktime")},
        )
    response.raise_for_status()
    job_id = response.json()["job_id"]
    assert job_id, "analyze response is missing job_id"
    return job_id


def _poll(client: httpx.Client, job_id: str, budget_s: float) -> tuple[dict, float]:
    start = time.monotonic()
    while True:
        response = client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY or ""})
        response.raise_for_status()
        body = response.json()
        elapsed = time.monotonic() - start
        if body.get("status") != "processing":
            return body, elapsed
        if elapsed > budget_s:
            raise AssertionError(f"job did not leave 'processing' within {budget_s:.0f} s")
        time.sleep(POLL_INTERVAL_S)


@pytest.mark.parametrize("clip", _clip_params())
def test_clip_processes_within_budget_and_matches_contract(
    client: httpx.Client, clip: Path
) -> None:
    job_id = _analyze(client, clip)
    body, runtime_s = _poll(client, job_id, JOB_BUDGET_S)

    assert runtime_s < JOB_BUDGET_S, (
        f"{clip.stem}: took {runtime_s:.1f} s (budget {JOB_BUDGET_S:.0f} s)"
    )
    assert body.get("status") != "failed", (
        f"{clip.stem}: job failed ({body.get('error', 'no reason given')})"
    )
    assert body.get("status") == "done", f"{clip.stem}: unexpected status {body.get('status')!r}"

    try:
        done = DoneJob.model_validate(body)
    except ValidationError as exc:
        raise AssertionError(
            f"{clip.stem}: response does not match contracts.DoneJob: {exc}"
        ) from exc

    for violation in done.violations:
        assert violation.evidence_frames, f"{clip.stem}: violation has no evidence frames"
        assert 1 <= len(violation.evidence_frames) <= 3
        for frame in violation.evidence_frames:
            raw = base64.b64decode(frame.image_base64, validate=True)
            assert raw.startswith(b"\xff\xd8\xff"), f"{clip.stem}: evidence frame is not a JPEG"
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()  # raises if Pillow cannot decode it as a real image

        # Norm fields the UI's norm block needs (implementation-plan.md WP4).
        assert violation.rule_id, f"{clip.stem}: violation missing rule_id"
        assert violation.source, f"{clip.stem}: violation missing source"
        assert violation.source_url, f"{clip.stem}: violation missing source_url"
        assert violation.citation_status in ("verified", "pending", "invalid"), (
            f"{clip.stem}: violation has no/invalid citation_status"
        )

    coverage_mode = done.coverage.mode if done.coverage else "n/a"
    print(
        f"{clip.stem}: verdict={done.verdict} violations={len(done.violations)} "
        f"runtime_s={runtime_s:.1f} coverage_mode={coverage_mode}"
    )
