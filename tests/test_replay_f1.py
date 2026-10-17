import json

import pytest

from scripts.replay_f1 import timing


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def test_timing_scores_all_anchors_but_weights_each_clip_once(tmp_path, capsys):
    labels = write_jsonl(
        tmp_path / "labels.jsonl",
        [
            {
                "sha256": sha,
                "original_id": sha,
                "organizer_verdict": verdict,
                "organizer_timestamps": times,
            }
            for sha, verdict, times in [
                ("caught-a", "violation", [10, 20]),
                ("caught-b", "violation", [10]),
                ("missed", "violation", [10]),
                ("untimed", "violation", []),
                ("clean", "no_violation", []),
            ]
        ],
    )
    first = {"rule_id": "A", "t": 15.0}
    best = {"rule_id": "A", "t": 19.0}
    other = {"rule_id": "B", "t": 22.0}
    results = write_jsonl(
        tmp_path / "replay.jsonl",
        [
            {
                "sha256": "caught-a",
                "findings": [first, best, other],
                "ranked_findings": [other, best, first],
            },
            {
                "sha256": "caught-b",
                "findings": [{"rule_id": "B", "t": 13.0}],
                "ranked_findings": [{"rule_id": "B", "t": 13.0}],
            },
            {"sha256": "missed", "findings": []},
            {"sha256": "untimed", "findings": [first]},
            {"sha256": "clean", "findings": [first]},
            {"sha256": "unknown", "findings": [first]},
        ],
    )

    timing(results, labels)
    output = capsys.readouterr()
    a, b, summary = map(json.loads, output.out.splitlines())
    assert a["original_id"] == "caught-a"
    assert [f["offset_sec"] for f in a["anchors"]] == [5.0, -1.0, 2.0]
    assert a["anchors"][1]["reference_sec"] == 20
    assert a["best_abs_offset_sec"] == 1.0
    assert a["top1"]["rule_id"] == "B"
    assert b["best_abs_offset_sec"] == 3.0
    assert summary["caught_violations"] == 3
    assert summary["missed_violations"] == 1
    assert summary["missing_timestamps"] == 1
    assert summary["best"] == {
        "clips": 2,
        "mean_abs_offset_sec": 2.0,
        "mean_offset_sec": 1.0,
        "within_s": {"1": 1, "2": 1, "3": 2, "5": 2},
    }
    assert summary["top1"]["mean_abs_offset_sec"] == 2.5
    assert summary["top1"]["within_s"] == {"1": 0, "2": 1, "3": 2, "5": 2}
    assert summary["per_rule"]["A"]["clips"] == 1
    assert summary["per_rule"]["A"]["mean_abs_offset_sec"] == 1.0
    assert "unlabelled cache entry unknown" in output.err


def test_timing_does_not_mistake_legacy_replay_order_for_service_ranking(tmp_path, capsys):
    labels = write_jsonl(
        tmp_path / "labels.jsonl",
        [
            {
                "sha256": "clip",
                "original_id": "clip",
                "organizer_verdict": "violation",
                "organizer_timestamps": [10],
            }
        ],
    )
    results = write_jsonl(
        tmp_path / "replay.jsonl",
        [{"sha256": "clip", "findings": [{"rule_id": "A", "t": 10}]}],
    )
    timing(results, labels)
    clip, summary = map(json.loads, capsys.readouterr().out.splitlines())
    assert clip["top1"] is None
    assert summary["best"]["within_s"] == {"1": 1, "2": 1, "3": 1, "5": 1}
    assert summary["top1"]["clips"] == 0
    assert summary["top1"]["mean_abs_offset_sec"] is None


@pytest.mark.parametrize("conflicting_verdict", [False, True])
def test_timing_retains_different_labels_for_identical_video_files(
    tmp_path, capsys, conflicting_verdict
):
    labels = write_jsonl(
        tmp_path / "labels.jsonl",
        [
            {
                "sha256": "same-file",
                "original_id": identity,
                "organizer_verdict": (
                    "no_violation" if conflicting_verdict and timestamp == 20 else "violation"
                ),
                "organizer_timestamps": [timestamp],
            }
            for identity, timestamp in [("first-name", 10), ("second-name", 20)]
        ],
    )
    results = write_jsonl(
        tmp_path / "replay.jsonl",
        [{"sha256": "same-file", "findings": [{"rule_id": "A", "t": 9}]}],
    )
    if conflicting_verdict:
        with pytest.raises(ValueError, match="Conflicting verdicts"):
            timing(results, labels)
        return
    timing(results, labels)
    clip, summary = map(json.loads, capsys.readouterr().out.splitlines())
    assert clip["original_ids"] == ["first-name", "second-name"]
    assert clip["organizer_timestamps"] == [10, 20]
    assert clip["best_abs_offset_sec"] == 1
    assert summary["caught_violations"] == 1


def test_timing_does_not_round_an_offset_into_the_tolerance_window(tmp_path, capsys):
    labels = write_jsonl(
        tmp_path / "labels.jsonl",
        [
            {
                "sha256": "clip",
                "original_id": "clip",
                "organizer_verdict": "violation",
                "organizer_timestamps": [10],
            }
        ],
    )
    results = write_jsonl(
        tmp_path / "replay.jsonl",
        [{"sha256": "clip", "findings": [{"rule_id": "A", "t": 13.0004}]}],
    )
    timing(results, labels)
    _, summary = map(json.loads, capsys.readouterr().out.splitlines())
    assert summary["best"]["within_s"] == {"1": 0, "2": 0, "3": 0, "5": 1}


def test_run_records_the_service_ranking_separately_from_rule_order(tmp_path, monkeypatch, capsys):
    from backend.f1 import events, rules
    from scripts.replay_f1 import run

    monkeypatch.setenv("API_KEY", "x")
    monkeypatch.setattr(events, "build_events", lambda *args: events.EventLog([], {}, [], {}))
    findings = [
        rules.Finding("L-NO-CASH-ON-LEAVE", 0, confidence=0.2),
        rules.Finding("W-NO-FOOD", 0.5, confidence=1),
    ]
    monkeypatch.setattr(rules, "evaluate_rules", lambda ctx: findings)
    cache = tmp_path / "clip"
    cache.mkdir()
    (cache / "perception.json").write_text(
        json.dumps(
            {
                "scene": {"objects": {}},
                "observations": [{"timestamp_sec": 0, "detections": []}],
            }
        )
    )
    run(tmp_path, None)
    record = json.loads(capsys.readouterr().out)
    assert record["findings"][0]["rule_id"] == "L-NO-CASH-ON-LEAVE"
    assert record["ranked_findings"][0] == {"rule_id": "W-NO-FOOD", "t": 0.5, "rank_score": 1.0}


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf")])
def test_timing_rejects_invalid_timestamps(tmp_path, invalid):
    labels = write_jsonl(
        tmp_path / "labels.jsonl",
        [
            {
                "sha256": "clip",
                "original_id": "clip",
                "organizer_verdict": "violation",
                "organizer_timestamps": [10],
            }
        ],
    )
    results = write_jsonl(
        tmp_path / "replay.jsonl",
        [{"sha256": "clip", "findings": [{"rule_id": "A", "t": invalid}]}],
    )
    with pytest.raises(ValueError, match="finite nonnegative"):
        timing(results, labels)
