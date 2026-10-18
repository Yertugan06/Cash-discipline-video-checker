"""`eval.export_gateway_run`: a saved gateway run -> the results directory `eval.run_eval` and
`eval.check_outputs` read. Synthetic items only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.export_gateway_run import export


def _item(name: str, status: str = "done", **extra) -> dict:
    item = {
        "id": name,
        "name": name,
        "source": "folder",
        "status": status,
        "job_id": "j-" + name,
        "label": "violation",
        "error": None,
        "started_at": 100.0,
        "finished_at": 142.34,
        "result": {
            "job_id": "j-" + name,
            "status": "done",
            "verdict": "no_violation",
            "violations": [],
        },
    }
    return item | extra


def test_writes_result_and_wall_time_and_no_label(tmp_path: Path):
    assert export([_item("Х-3.mov")], tmp_path) == 1  # Cyrillic Х in the file name
    assert json.loads((tmp_path / "X-3.json").read_text())["verdict"] == "no_violation"
    assert json.loads((tmp_path / "X-3.meta.json").read_text()) == {"wall_s": 42.3}
    assert "label" not in (tmp_path / "X-3.json").read_text()


def test_failed_item_becomes_a_failed_job(tmp_path: Path):
    export(
        [_item("X-4.mov", status="failed", result=None, error="no result after 300 s")], tmp_path
    )
    assert json.loads((tmp_path / "X-4.json").read_text()) == {
        "job_id": "j-X-4.mov",
        "status": "failed",
        "error": "no result after 300 s",
    }


def test_refuses_an_unfinished_run(tmp_path: Path):
    with pytest.raises(ValueError, match="still pending: X-5.mov"):
        export([_item("X-1.mov"), _item("X-5.mov", status="processing")], tmp_path)
    assert not list(tmp_path.iterdir())


def test_refuses_two_items_for_one_clip(tmp_path: Path):
    with pytest.raises(ValueError, match="two items for X-1"):
        export([_item("X-1.mov"), _item("Х-1.mov")], tmp_path)
