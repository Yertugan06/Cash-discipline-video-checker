"""`VlmSettings`: configuration for `VlmDetector` (SHARED_BRIEF.md "Agreed interfaces").

Every field but `model` has a default so WP1's `backend.config.Settings` can
build this from `VLM_*` env vars without requiring all of them to be set.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VlmSettings(BaseModel):
    """Everything `VlmDetector`, its sampler and its client need to run.

    Field meanings follow architecture.md §4-§6:
      - `max_side`: long edge, px, the frame is resized to before being sent
        (architecture.md §6 lever 4; matches the kit's `--max-side 768`).
      - `max_in_flight`: concurrent requests to vLLM (architecture.md §4:
        "up to 8-16 frame requests are in flight, so vLLM batches them").
      - `request_timeout_s`: per-request HTTP timeout.
      - `stop_margin_s`: the sampler stops issuing new requests at
        `plan.deadline_monotonic - stop_margin_s` (architecture.md §4 step 3).
      - `max_failed_frac`: above this fraction of failed frames, the detector
        raises `TooManyFailedFramesError` instead of returning a result
        (architecture.md §7).
      - `fill_step_s`: only used to report `Coverage.step_s` when the fill
        pass completed; WP1's `backend.plan.build_plan` is what actually
        builds the fill grid.
    """

    base_url: str = "http://127.0.0.1:8010/v1"
    model: str
    max_side: int = 768
    max_in_flight: int = Field(default=8, gt=0)
    request_timeout_s: float = Field(default=60.0, gt=0)
    stop_margin_s: float = Field(default=15.0, ge=0)
    max_failed_frac: float = Field(default=0.30, ge=0, le=1)
    fill_step_s: float = Field(default=2.0, gt=0)

    # Not in the brief's minimal list, but needed to drive the OpenAI-compatible
    # client; all have defaults so existing call sites keep working.
    api_key: str = "EMPTY"  # vLLM ignores the value; the header is just expected to be present.
    temperature: float = 0.0
    max_tokens: int = 500
    structured_output: Literal["json_schema", "guided_json"] = "json_schema"
    readiness_timeout_s: float = Field(default=5.0, gt=0)
