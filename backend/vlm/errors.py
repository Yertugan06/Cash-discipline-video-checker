"""VLM-detector error hierarchy (SHARED_BRIEF.md "Agreed interfaces"; architecture.md §7).

Every failure that should turn a job into an explicit `failed` result (never a
fabricated `no_violation`, AGENTS.md "Avoid ... invented mock results") is one
of these.
"""

from __future__ import annotations


class VlmError(RuntimeError):
    """Base class for all VLM-detector failures."""


class VlmUnavailableError(VlmError):
    """vLLM is unreachable: connection refused or timed out.

    Raised by `backend.vlm.client` when a request cannot even reach the
    server, and propagated unchanged through `backend.vlm.sampler` and
    `backend.vlm.detector.VlmDetector.detect`. Never retried: a schema-invalid
    answer is a different, retried, failure mode (see `TooManyFailedFramesError`).
    """


class TooManyFailedFramesError(VlmError):
    """More than `VlmSettings.max_failed_frac` of the attempted frames failed.

    Raised by `VlmDetector.detect` after the sampler returns, once the
    fraction of `StateTimeline.coverage.failed` over `coverage.done` exceeds
    the configured threshold (architecture.md §7: "Over 30% failed frames →
    job failed with the reason").
    """
