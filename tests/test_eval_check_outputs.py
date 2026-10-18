"""`eval.check_outputs.check_clip` on synthetic job results."""

from __future__ import annotations

import base64

from eval.check_outputs import check_clip

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0fake").decode()


def _done(*violations, verdict="violation"):
    return {"job_id": "j", "status": "done", "verdict": verdict, "violations": list(violations)}


def _v(t, description="На столе видны наличные.", frame=JPEG):
    return {"type": "Тип", "timecode_sec": t, "description": description, "rule_id": "R",
            "evidence_frames": [{"timestamp_sec": t, "image_base64": frame}],
            "source": "231, п. 20", "source_url": "https://adilet.zan.kz/x",
            "citation_status": "pending"}  # fmt: skip


def test_true_positive_with_timing_and_evidence():
    row = check_clip(_done(_v(12.0), _v(40.0)), {"violation": True, "times": [11.0]}, 42.0)
    assert row["outcome"] == "TP" and row["schema"] == "ok" and not row["over_limit"]
    assert [f["delta_s"] for f in row["findings"]] == [1.0, 29.0]
    assert all(f["frames_jpeg"] and f["description_filled"] for f in row["findings"])


def test_flags_unfilled_templates_bad_frames_and_slow_jobs():
    bad = _v(5.0, description="С {t_start} по {t_end} с", frame="aGVsbG8=")
    row = check_clip(_done(bad), {"violation": False, "times": []}, 310.0)
    assert row["outcome"] == "FP" and row["over_limit"]
    f = row["findings"][0]
    assert not f["frames_jpeg"] and not f["description_filled"] and f["delta_s"] is None


def test_schema_and_failure_paths():
    assert check_clip({"job_id": "j", "status": "done"}, {"violation": True, "times": []}, None)[
        "schema"
    ].startswith("INVALID")
    failed = {"job_id": "j", "status": "failed", "error": "boom"}
    assert check_clip(failed, {"violation": True, "times": [1.0]}, 3.0)["outcome"] == "FAILED"
    assert (
        check_clip(_done(verdict="no_violation"), {"violation": True, "times": [1.0]}, 3.0)[
            "outcome"
        ]
        == "FN"
    )
