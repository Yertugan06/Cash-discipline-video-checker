import json

from backend.eval_runner import write_progress
from scripts.serve_model_results import progress


def test_model_report_progress_and_failure(tmp_path):
    assert progress(tmp_path, "L4")["stage"] == "building"
    models = tmp_path / "model-check"
    models.mkdir()
    (models / "run.log").write_text("loading", encoding="utf-8")
    assert progress(tmp_path, "L4")["stage"] == "models"
    (models / "result.json").write_text(json.dumps({"status": "passed"}))
    status = progress(tmp_path, "L4")
    assert status["stage"] == "pipeline" and status["models_ready"]
    pipeline = tmp_path / "synthetic-pipeline"
    pipeline.mkdir()
    (pipeline / "result.json").write_text(json.dumps({"status": "passed"}))
    assert progress(tmp_path, "L4")["stage"] == "done"
    (pipeline / "result.json").write_text(json.dumps({"status": "failed"}))
    assert progress(tmp_path, "L4")["stage"] == "failed"
    write_progress(tmp_path / "gpu", 2, [], ["X-1"])
    status = progress(tmp_path, "L4")
    assert status["stage"] == "evaluating" and status["evaluation"]["completed"] == 0
    rows = [{"aliases": ["X-1"], "status": "failed", "end_to_end_sec": 1.5}]
    write_progress(tmp_path / "gpu", 1, rows, None)
    status = progress(tmp_path, "L4")
    assert status["stage"] == "evaluated" and status["evaluation"]["failed"] == 1
