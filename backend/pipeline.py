"""Pure orchestration: probe -> build_plan -> detect -> rank -> ground -> evidence -> serialize.

`Pipeline` holds the long-lived collaborators (detector, rank, knowledge)
that the app builds once at startup; `run()` is the one call per job. No
persistence here -- that is `backend.store.JobStore`'s job, driven by
`backend.worker.Worker`.
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

    def run(self, job_id: str, video: Path, deadline_monotonic: float) -> DoneJob:
        info = probe(video)
        logger.info("job %s probe: %.1f s", job_id, info.duration_sec)
        sampling_plan = build_plan(info, deadline_monotonic)
        result = self.detector.detect(video, info, sampling_plan)
        logger.info(
            "job %s detect: %d findings, coverage %s",
            job_id,
            len(result.findings),
            result.coverage.model_dump(),
        )
        ranked = self.rank(result.findings, self.knowledge.enabled_rules(), self.rank_cap)
        logger.info("job %s rank: %s", job_id, [(f.rule_id, round(f.t_anchor, 1)) for f in ranked])
        grounded = self.knowledge.ground(ranked)
        frames = evidence.collect(video, grounded, max(0.0, info.duration_sec - 1.0 / info.fps))
        done = serialize.to_done_job(job_id, grounded, result, frames, self.knowledge.describe)
        logger.info("job %s verdict: %s", job_id, done.verdict)
        return done
