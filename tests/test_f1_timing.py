from copy import deepcopy

import pytest

from backend.config import Settings
from backend.f1.detector import F1Detector
from backend.f1.rules import RULES
from backend.knowledge import Knowledge
from backend.rules import rank
from tests.test_f1_rules import COLLECT, context, event


def test_seal_check_anchors_when_collector_leaves_before_inspection():
    finding = RULES["K-SEAL-CHECK"](context(COLLECT))[0]
    assert finding.timestamp_sec == 9
    assert finding.facts["handover_sec"] == 5


@pytest.mark.parametrize("visible_on_exit", [False, True])
def test_seal_check_does_not_reuse_handover_geometry_at_exit(visible_on_exit):
    events = deepcopy(COLLECT)
    old_box = [0.1, 0.2, 0.2, 0.3]
    events[1].facts["box"] = old_box
    ctx = context(events)
    if not visible_on_exit:
        ctx.observations = [
            frame.model_copy(update={"detections": []}) for frame in ctx.observations
        ]
    finding = RULES["K-SEAL-CHECK"](ctx)[0]
    if visible_on_exit:
        bag = next(d for d in ctx.nearby(9).detections if d.track_id == "bag:1")
        assert finding.facts["box"] == list(bag.box)
        assert finding.facts["box"] != old_box
    else:
        assert "box" not in finding.facts


def test_confirmed_exit_breaks_a_tie_between_the_same_leave_rule(tmp_path):
    ctx = context(
        [
            event("WORKSTATION_AWAY_START", 2, condition_id="away", actor_id="cashier"),
            event("WORKSTATION_AWAY_END", 5, condition_id="away", actor_id="cashier"),
            event("WORKSTATION_AWAY_START", 8, condition_id="away", actor_id="cashier"),
            event("WORKSTATION_AWAY_END", 11, condition_id="away", actor_id="cashier"),
            event("EXIT", 10, actor_id="cashier", role="cashier"),
        ]
    )
    findings = RULES["L-NO-CASH-ON-LEAVE"](ctx)
    assert [f.timestamp_sec for f in findings] == [2, 8]
    assert [f.facts["confirmed_exit"] for f in findings] == [False, True]
    rules = Knowledge.load(Settings(api_key="x").knowledge_dir).enabled_rules()
    detector = F1Detector(Settings(api_key="x", work_dir=tmp_path), rules)
    ranked = rank([detector._to_finding(f, ctx.duration) for f in findings], rules)
    assert [f.t_anchor for f in ranked] == [8, 2]


@pytest.mark.parametrize(
    "exit_at,actor,role,confirmed",
    [
        (4, "cashier", "cashier", True),
        (4, "other", "cashier", False),
        (4, "cashier", "client", False),
        (6, "cashier", "cashier", False),
    ],
)
def test_only_the_cashiers_exit_during_this_absence_confirms_departure(
    exit_at, actor, role, confirmed
):
    ctx = context(
        [
            event("WORKSTATION_AWAY_START", 2, condition_id="away", actor_id="cashier"),
            event("EXIT", exit_at, actor_id=actor, role=role),
            event("WORKSTATION_AWAY_END", 5, condition_id="away", actor_id="cashier"),
        ]
    )
    findings = RULES["L-NO-CASH-ON-LEAVE"](ctx)
    assert findings[0].facts["confirmed_exit"] is confirmed


def test_direct_cashier_exit_is_confirmed_without_an_away_interval():
    ctx = context([event("EXIT", 5, actor_id="cashier", role="cashier")])
    finding = RULES["L-NO-CASH-ON-LEAVE"](ctx)[0]
    assert finding.timestamp_sec == 5
    assert finding.facts["confirmed_exit"] is True
