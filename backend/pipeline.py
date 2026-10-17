"""Pure orchestration: probe -> build_plan -> detect -> rank -> ground -> evidence -> serialize.

`Pipeline` holds the long-lived collaborators (detector, rank, knowledge)
that the app builds once at startup; `run()` is the one call per job. No
persistence here -- that is `backend.store.JobStore`'s job, driven by
`backend.worker.Worker`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend import evidence, serialize
from backend.contracts import Detector, DoneJob, Finding, GroundedFinding, RuleEntry
from backend.media import probe
from backend.plan import build_plan

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
        sampling_plan = build_plan(info, deadline_monotonic)
        result = self.detector.detect(video, info, sampling_plan)
        ranked = self.rank(result.findings, self.knowledge.enabled_rules(), self.rank_cap)
        grounded = self.knowledge.ground(ranked)
        frames = evidence.collect(video, grounded)
        return serialize.to_done_job(job_id, grounded, result, frames, self.knowledge.describe)
