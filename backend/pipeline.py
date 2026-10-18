"""Pure orchestration: probe -> build_plan -> detect -> rank -> ground -> evidence -> serialize.

`Pipeline` holds the long-lived collaborators (detector, rank, knowledge)
that the app builds once at startup; `run()` is the one call per job. No
persistence here -- that is `backend.store.JobStore`'s job, driven by
`backend.worker.Worker`.

The detector gets the job deadline minus `finalize_reserve_s`, so ranking,
evidence frames and serialization still fit before the job deadline. A
detection cut short by the deadline (`coverage.mode == "partial"`) keeps its
findings; without findings it raises `IncompleteAnalysisError` instead of
reporting «no violation» for a video it did not fully see.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend import evidence, serialize
from backend.contracts import Detector, DoneJob, Finding, GroundedFinding, RuleEntry
from backend.media import probe
from backend.plan import build_plan

logger = logging.getLogger(__name__)


class IncompleteAnalysisError(RuntimeError):
    """The deadline cut detection short and nothing was found in the part that was seen."""


RankFn = Callable[[list[Finding], list[RuleEntry], int], list[Finding]]


class KnowledgeLike(Protocol):
    """What `Pipeline` needs from WP3's `Knowledge`; a fake satisfies this in tests."""

    def enabled_rules(self) -> list[RuleEntry]: ...

    def ground(self, findings: list[Finding]) -> list[GroundedFinding]: ...

    def describe(self, grounded: GroundedFinding) -> str: ...


@dataclass(frozen=True)
class Pipeline:
    detector: Detector
    rank: RankFn
    knowledge: KnowledgeLike
    rank_cap: int = 3
    finalize_reserve_s: float = 15.0

    def run(self, job_id: str, video: Path, deadline_monotonic: float) -> DoneJob:
        info = probe(video)
        logger.info("job %s probe: %.1f s", job_id, info.duration_sec)
        sampling_plan = build_plan(info, deadline_monotonic - self.finalize_reserve_s)
        result = self.detector.detect(video, info, sampling_plan)
        coverage = result.coverage
        logger.info(
            "job %s detect: %d findings, coverage %s",
            job_id,
            len(result.findings),
            coverage.model_dump(),
        )
        if not result.findings and coverage.mode == "partial":
            raise IncompleteAnalysisError(
                f"Analysis incomplete: the time limit was reached after {coverage.done} of "
                f"{coverage.planned} planned frames and nothing was found in that part; "
                "no «no violation» verdict is given for a video that was not fully analysed"
            )
        ranked = self.rank(result.findings, self.knowledge.enabled_rules(), self.rank_cap)
        logger.info("job %s rank: %s", job_id, [(f.rule_id, round(f.t_anchor, 1)) for f in ranked])
        grounded = self.knowledge.ground(ranked)
        frames = evidence.collect(video, grounded, max(0.0, info.duration_sec - 1.0 / info.fps))
        done = serialize.to_done_job(job_id, grounded, result, frames, self.knowledge.describe)
        logger.info("job %s verdict: %s", job_id, done.verdict)
        return done
