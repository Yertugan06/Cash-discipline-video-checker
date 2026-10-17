"""OpenAI-compatible chat-completions client for the vLLM questionnaire server.

architecture.md §4/§6 and SHARED_BRIEF.md: the fixed form text goes first and
the image last, so vLLM's prefix cache covers the long, fixed instructions
across every frame of every job; only the trailing time stamp and the image
differ between requests (`backend/vlm/prompts/questionnaire.txt` puts the
`{t}` placeholder at the very end for the same reason).

Failure handling (architecture.md §2 "Discovery", §7):
  - a connection-level failure (refused / timed out) means vLLM itself is not
    answering at all -> `VlmUnavailableError`, not retried here;
  - a schema-invalid answer (bad JSON, failed `FrameState` validation, a
    non-200 HTTP status) is retried once with an extra reminder, then
    returned as `FrameObservation(ok=False, error=...)` for the sampler to
    count towards `coverage.failed`.
"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from pydantic import ValidationError

from backend.contracts import FrameObservation, FrameState
from backend.vlm.config import VlmSettings
from backend.vlm.errors import VlmUnavailableError

_RETRY_HINT = "Return strictly valid JSON matching the schema."


def check_ready(settings: VlmSettings, *, client: httpx.Client | None = None) -> bool:
    """True iff the vLLM server answers `GET {base_url}/models`.

    Used by WP1's `/readyz`. Never raises: connection refused or a timeout
    simply means "not ready yet", not a hard error. `client` is injectable
    for tests (e.g. `httpx.Client(transport=httpx.MockTransport(...))`); the
    default opens a short-lived real client.
    """
    owns_client = client is None
    http_client = client or httpx.Client()
    try:
        resp = http_client.get(
            f"{settings.base_url.rstrip('/')}/models", timeout=settings.readiness_timeout_s
        )
    except httpx.TransportError:
        return False
    finally:
        if owns_client:
            http_client.close()
    return resp.status_code == 200


def ask_frame(
    http_client: httpx.Client,
    settings: VlmSettings,
    t: float,
    image_bytes: bytes,
    schema: dict[str, Any],
    system_prompt: str,
    questionnaire_prompt: str,
) -> FrameObservation:
    """Asks the questionnaire for one frame.

    Retries once (with a reminder appended, same image) if the first answer
    is not valid JSON or does not validate against `FrameState`. Raises
    `VlmUnavailableError` immediately on a connection-level failure, on
    either attempt.
    """
    body = _build_body(settings, t, image_bytes, schema, system_prompt, questionnaire_prompt)
    t0 = time.monotonic()
    state, error = _ask_once(http_client, settings, body)
    if state is None:
        state, error = _ask_once(http_client, settings, _with_retry_hint(body))
    latency = time.monotonic() - t0
    if state is None:
        return FrameObservation(t=t, ok=False, state=None, error=error, latency_s=latency)
    return FrameObservation(t=t, ok=True, state=state, error=None, latency_s=latency)


def _build_body(
    settings: VlmSettings,
    t: float,
    image_bytes: bytes,
    schema: dict[str, Any],
    system_prompt: str,
    questionnaire_prompt: str,
) -> dict[str, Any]:
    question = questionnaire_prompt.replace("{t}", f"{t:.1f}")
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
    content: list[dict[str, Any]] = [
        {"type": "text", "text": question},  # fixed form text first (prefix-cached)
        {"type": "image_url", "image_url": {"url": data_url}},  # image last
    ]
    body: dict[str, Any] = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
    }
    if settings.structured_output == "json_schema":
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "frame_state", "schema": schema, "strict": True},
        }
    else:  # guided_json: older vLLM releases (see deploy/vllm/requirements-vllm.txt)
        body["guided_json"] = schema
    return body


def _with_retry_hint(body: dict[str, Any]) -> dict[str, Any]:
    """Same request, with a short reminder inserted before the image (kept last)."""
    text_item, image_item = body["messages"][1]["content"]
    retry_content = [text_item, {"type": "text", "text": _RETRY_HINT}, image_item]
    retry_body = dict(body)
    retry_body["messages"] = [
        body["messages"][0],
        {"role": "user", "content": retry_content},
    ]
    return retry_body


def _ask_once(
    http_client: httpx.Client, settings: VlmSettings, body: dict[str, Any]
) -> tuple[FrameState | None, str | None]:
    raw, error = _post_once(http_client, settings, body)
    if raw is None:
        return None, error
    try:
        return FrameState.model_validate_json(raw), None
    except ValidationError as exc:
        return None, f"schema validation failed: {exc}"
    except ValueError as exc:  # JSONDecodeError is a ValueError subclass
        return None, f"invalid JSON: {exc}"


def _post_once(
    http_client: httpx.Client, settings: VlmSettings, body: dict[str, Any]
) -> tuple[str | None, str | None]:
    try:
        resp = http_client.post(
            "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=settings.request_timeout_s,
        )
    except httpx.TransportError as exc:
        raise VlmUnavailableError(f"vLLM unreachable: {exc}") from exc
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:300]!r}"
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    return content or "", None
