"""Equivalence test: `backend.rules.evaluate` vs. the kit's `timeline_rules.detect()` (the
reference oracle), run over every saved state file.

Privacy: this test only ever prints rule names and timestamps (never a frame's field values).
`KIT_STATES_DIR` overrides the default location; the default kit tree is gitignored private
research material, so the test skips with a clear reason when it is absent.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from backend.contracts import RuleEntry, StateTimeline
from backend.knowledge import Knowledge
from backend.rules import evaluate
from eval.kit_states_adapter import load_kit_states

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATES_DIR = (
    REPO_ROOT
    / "archive"
    / "vm-copies"
    / "datathon"
    / "forte_brev_kit"
    / "brev_kit"
    / "runs"
    / "q35_9b_fp8"
    / "states"
)
KIT_TIMELINE_RULES = (
    REPO_ROOT
    / "archive"
    / "vm-copies"
    / "datathon"
    / "forte_brev_kit"
    / "brev_kit"
    / "scripts"
    / "timeline_rules.py"
)

# Kit short name -> canonical rule_id, per architecture.md §3. Only this test needs the kit's
# names at all; production code (backend/rules/timeline.py) speaks canonical ids directly.
KIT_TO_CANONICAL = {
    "leave_cash": "L-NO-CASH-ON-LEAVE",
    "leave_key": "L-SAFE-LOCKED-ON-LEAVE",
    "leave_laptop": "L-PC-LOCKED",
    "leave_docs": "L-NO-DOCS-ON-LEAVE",
    "safe_open": "S-SAFE-CLOSED",
    "dirty_desk": "S-CLEAN-DESK-HANDOVER",
    "merge_cash": "S-NO-MERGE",
    "outsider": "A-OUTSIDER-ZONE",
    "door_open": "A-DOOR-LOCK",
    "two_clients": "A-SECOND-PERSON",
    "client_left_count": "C-COUNT-BEFORE-EXIT",
    "no_id": "C-ID-BEFORE-CASH",
    "no_detector": "C-DETECTOR-CHECK",
    "personal_items": "W-NO-PERSONAL-ITEMS",
    "food": "W-NO-FOOD",
    "phone": "W-NO-CAMERA-PHONE",
    "collector_quick": "K-SEAL-CHECK",
    "bag_to_safe_no_count": "K-RECOUNT-BEFORE-SAFE",
}

TIME_TOLERANCE_S = 1e-6


def _states_dir() -> Path:
    override = os.environ.get("KIT_STATES_DIR")
    return Path(override) if override else DEFAULT_STATES_DIR


def _load_kit_detect():
    if not KIT_TIMELINE_RULES.exists():
        pytest.skip(f"kit timeline_rules.py not present at {KIT_TIMELINE_RULES} (gitignored)")
    spec = importlib.util.spec_from_file_location("kit_timeline_rules", KIT_TIMELINE_RULES)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.detect


def _all_enabled_rules(knowledge: Knowledge) -> list[RuleEntry]:
    """Every canonical rule, all enabled -- the oracle is run with `experimental=True`, so our
    port must evaluate C-DETECTOR-CHECK too, even though it stays disabled in production."""
    return [r.model_copy(update={"enabled": True}) for r in knowledge.rules]


def _kit_samples(timeline: StateTimeline) -> list[dict]:
    """Reproduce the kit's own state-file loader filter: ok and a dict state, sorted by t."""
    samples = []
    for fo in timeline.frames:
        if fo.ok and fo.state is not None:
            samples.append({"t": fo.t, "state": fo.state.model_dump()})
    samples.sort(key=lambda s: s["t"])
    return samples


def _state_files() -> list[Path]:
    d = _states_dir()
    if not d.is_dir():
        return []
    return sorted(d.glob("*.jsonl"))


@pytest.mark.parametrize("state_file", _state_files(), ids=lambda p: p.stem)
def test_port_matches_kit_oracle(state_file: Path) -> None:
    detect = _load_kit_detect()
    knowledge = Knowledge.load(REPO_ROOT / "knowledge")
    rules = _all_enabled_rules(knowledge)

    timeline = load_kit_states(state_file)

    oracle_raw, _obs = detect(_kit_samples(timeline), params=None, experimental=True)
    oracle = sorted((KIT_TO_CANONICAL[v["rule"]], round(v["t"], 2)) for v in oracle_raw)

    ours_findings = evaluate(timeline, rules)
    ours = sorted((f.rule_id, round(f.t_anchor, 2)) for f in ours_findings)

    if len(oracle) != len(ours):
        oracle_ids = sorted({r for r, _ in oracle})
        our_ids = sorted({r for r, _ in ours})
        pytest.fail(
            f"{state_file.stem}: {len(oracle)} oracle findings vs {len(ours)} ours "
            f"(rule_ids oracle={oracle_ids} ours={our_ids})"
        )
    for (o_rule, o_t), (r_rule, r_t) in zip(oracle, ours, strict=True):
        assert o_rule == r_rule, f"{state_file.stem}: rule mismatch {o_rule!r} vs {r_rule!r}"
        assert abs(o_t - r_t) <= TIME_TOLERANCE_S, (
            f"{state_file.stem}: rule {o_rule!r} time mismatch {o_t} vs {r_t}"
        )


def test_state_files_present_or_skipped() -> None:
    if not _state_files():
        pytest.skip(f"no kit state files under {_states_dir()} (set KIT_STATES_DIR to override)")


if __name__ == "__main__":
    # Manual run: report N/40 identical, without pytest's per-parametrize noise.
    files = _state_files()
    if not files:
        print(json.dumps({"skipped": True, "reason": str(_states_dir())}))
    else:
        ok = 0
        for f in files:
            try:
                test_port_matches_kit_oracle(f)
                ok += 1
            except AssertionError:
                pass
        print(f"{ok}/{len(files)} videos identical")
