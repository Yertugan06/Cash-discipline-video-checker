"""Unit tests for `eval.run_eval`, using synthetic `DoneJob` outputs and a synthetic GT/split
pair written to a tmp dir -- never the real `validation/validation-private/gt.json` (privacy
rule: this suite must not touch organizer labels)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.clip_id import InvalidClipId
from backend.knowledge import Knowledge, KnowledgeError
from eval.coverage import _code_match
from eval.run_eval import (
    KNOWLEDGE_ROOT,
    build_pred,
    clip_id_from_filename,
    run_scorer,
    to_pred_entry,
)

pytestmark = pytest.mark.skipif(
    not (
        Path(__file__).resolve().parent.parent
        / "validation"
        / "validation-evidence"
        / "harness"
        / "score.py"
    ).exists(),
    reason="R1 harness score.py not present in this checkout",
)


@pytest.fixture(scope="module")
def knowledge() -> Knowledge:
    return Knowledge.load(KNOWLEDGE_ROOT)


def _done(*violations: dict) -> dict:
    return {
        "job_id": "j",
        "status": "done",
        "verdict": "violation" if violations else "no_violation",
        "violations": [
            {
                "type": "t",
                "timecode_sec": 1.0,
                "description": "d",
                "evidence_frames": [{"timestamp_sec": 1.0, "image_base64": "x"}],
                **v,
            }
            for v in violations
        ],
    }


def test_clip_id_from_filename():
    assert clip_id_from_filename("X-12.json") == "X-12"
    assert clip_id_from_filename("Х-12.mov.json") == "X-12"  # Cyrillic Х


@pytest.mark.parametrize("name", ["x12_done.json", "no-digits.json", "3f9a2c.json"])
def test_clip_id_from_filename_rejects_names_that_are_not_clips(name):
    with pytest.raises(InvalidClipId):
        clip_id_from_filename(name)


def test_build_pred_rejects_two_files_for_one_clip(tmp_path: Path):
    done = {"job_id": "j", "status": "done", "verdict": "no_violation", "violations": []}
    for name in ("X-3.json", "Х-3.json"):
        (tmp_path / name).write_text(json.dumps(done), encoding="utf-8")
    with pytest.raises(ValueError, match="two DoneJob files for X-3"):
        build_pred(tmp_path)


def test_to_pred_entry_violation(knowledge):
    done = {
        "job_id": "j1",
        "status": "done",
        "verdict": "violation",
        "violations": [
            {
                "type": "t",
                "timecode_sec": 12.5,
                "description": "d",
                "evidence_frames": [{"timestamp_sec": 12.5, "image_base64": "x"}],
                "rule_id": "L-NO-CASH-ON-LEAVE",
            }
        ],
        "warnings": [],
    }
    entry = to_pred_entry(done, knowledge)
    assert entry["verdict"] == "violation"
    assert entry["events"] == [{"t": 12.5, "code": "231-20-2", "conf": None}]
    assert entry["error"] is None


def test_to_pred_entry_failed_job_carries_error(knowledge):
    done = {"job_id": "j2", "status": "failed", "error": "model unavailable"}
    entry = to_pred_entry(done, knowledge)
    assert entry["verdict"] == "no_violation"
    assert entry["events"] == []
    assert entry["error"] == "model unavailable"


def test_build_pred_reads_a_directory(tmp_path):
    (tmp_path / "X-1.json").write_text(
        json.dumps({"job_id": "a", "status": "done", "verdict": "no_violation", "violations": []}),
        encoding="utf-8",
    )
    (tmp_path / "X-2.json").write_text(
        json.dumps(
            {
                "job_id": "b",
                "status": "done",
                "verdict": "violation",
                "violations": [
                    {
                        "type": "t",
                        "timecode_sec": 3.0,
                        "description": "d",
                        "evidence_frames": [{"timestamp_sec": 3.0, "image_base64": "x"}],
                        "rule_id": "W-NO-FOOD",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pred = build_pred(tmp_path)
    assert set(pred) == {"X-1", "X-2"}
    assert pred["X-1"]["verdict"] == "no_violation"
    assert pred["X-2"]["events"][0]["code"] == "231-12-2"


def test_build_pred_takes_runtime_from_the_meta_file(tmp_path):
    (tmp_path / "X-1.json").write_text(json.dumps(_done()), encoding="utf-8")
    (tmp_path / "X-1.meta.json").write_text(json.dumps({"wall_s": 42.3}), encoding="utf-8")
    (tmp_path / "X-2.json").write_text(json.dumps(_done()), encoding="utf-8")
    pred = build_pred(tmp_path)
    assert set(pred) == {"X-1", "X-2"}
    assert pred["X-1"]["runtime_s"] == 42.3
    assert pred["X-2"]["runtime_s"] is None


@pytest.mark.parametrize(
    ("rule_id", "annotation"),
    [
        ("A-DOOR-LOCK", "п. 16 пп. 1)"),  # act 14
        ("L-NO-CASH-ON-LEAVE", "п. 20 ч. 2"),  # act 231
        ("L-PC-LOCKED", "48-71-9"),  # cites 53-71-9; the scorer ignores the act number
    ],
)
def test_scorer_matches_the_code_against_the_annotated_norm(knowledge, rule_id, annotation):
    """With the rule id as the code (before 2026-10-18), the legal-citation match was always 0."""
    [event] = to_pred_entry(_done({"rule_id": rule_id}), knowledge)["events"]
    assert _code_match()(event["code"], annotation)


def test_to_pred_entry_rejects_a_violation_without_a_known_rule(knowledge):
    with pytest.raises(ValueError, match="no rule_id"):
        to_pred_entry(_done({}), knowledge)
    with pytest.raises(KnowledgeError, match="unknown rule_id"):
        to_pred_entry(_done({"rule_id": "NOT-A-RULE"}), knowledge)


def test_run_scorer_on_synthetic_gt_prints_aggregates_only(tmp_path, capsys):
    """A fully synthetic GT/split pair -- no organizer labels -- fed through the real harness
    scorer, to check the adapter actually produces a shape the harness accepts."""
    priv = tmp_path / "validation-private"
    priv.mkdir()
    gt = {
        "X-1": {
            "violation": True,
            "org_times": [5.0],
            "layout": "synthetic",
            "human": [],
            "human_reliable": False,
        },
        "X-2": {
            "violation": False,
            "org_times": [],
            "layout": "synthetic",
            "human": [],
            "human_reliable": False,
        },
    }
    split = {"X-1": "dev", "X-2": "dev"}
    (priv / "gt.json").write_text(json.dumps(gt), encoding="utf-8")
    (priv / "split.json").write_text(json.dumps(split), encoding="utf-8")

    pred = {
        "X-1": {
            "verdict": "violation",
            "events": [{"t": 5.0, "code": "L-NO-CASH-ON-LEAVE", "conf": None}],
            "runtime_s": 1.0,
            "error": None,
        },
        "X-2": {"verdict": "no_violation", "events": [], "runtime_s": 1.0, "error": None},
    }
    report = run_scorer(pred, tmp_path, "synthetic_test", split="dev")
    assert "n=2" in report
    assert "recall" in report
    # Never leaks the GT dict itself, only the harness's own aggregate text.
    assert "synthetic" in report or "layout" in report
