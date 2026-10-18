"""Audit fixtures exercise reason/verdict independence without running or mocking inference."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from eval.audit_findings import audit, dump_json, main, make_manifest, run_manifest

OLD_CASH = "S-CLEAN-DESK-HANDOVER"
ID = "C-ID-BEFORE-CASH"
LEAVE = "L-NO-DOCS-ON-LEAVE"
PROVENANCE = {"id": "synthetic-human-account", "kind": "test_fixture_not_organizer_reason"}


def label(clip: int, sha: str = "a" * 64, positive: bool = True, t: float = 57) -> dict:
    return {
        "sha256": sha,
        "original_id": f"X-{clip}",
        "duration_sec": 100,
        "organizer_verdict": "violation" if positive else "no_violation",
        "organizer_timestamps": [t] if positive else [],
    }


def prediction(rule: str | None = None, t: float = 57, sha: str = "a" * 64) -> dict:
    return {"sha256": sha, "findings": [{"rule_id": rule, "t": t}] if rule else []}


def observation(clip_ids: list[str], rule: str, status: str, interval=None, **kwargs) -> dict:
    return {
        "clip_ids": clip_ids,
        "provenance_id": PROVENANCE["id"],
        "coverage": "partial",
        "events": [{"id": "observed-event", "interval_sec": interval}],
        "reason_checks": [
            {
                "rule_ids": [rule],
                "status": status,
                "event_ids": ["observed-event"],
                "explanation": "Fixture observation.",
            }
        ],
        **kwargs,
    }


def assertions(*clips: dict) -> dict:
    return {"schema_version": 1, "provenance": PROVENANCE, "clips": list(clips)}


def evaluate(labels: list[dict], predictions: list[dict], observed: dict | None = None) -> dict:
    return audit(
        "\n".join(json.dumps(row) for row in labels),
        [({"path": "explicit-replay.jsonl"}, "\n".join(json.dumps(row) for row in predictions))],
        observed if observed is not None else assertions(),
    )


def test_correct_binary_verdict_wrong_reason_never_gets_timing_credit():
    report = evaluate(
        [label(4), label(47, t=68)],
        [prediction(ID, 68)],
        assertions(observation(["X-4", "X-47"], ID, "contradicted", [57, 57])),
    )
    assert report["summary"]["unique_verdict_confusion"]["TP"] == 1
    assert report["summary"]["sample_verdict_confusion"]["TP"] == 2
    finding = report["clips"][0]["findings"][0]
    assert finding["reason_status"] == "contradicted"
    assert finding["compatible_event_timing"] == []
    assert [row["signed_offsets_sec"] for row in finding["organizer_offsets"]] == [[11], [0]]
    assert not any(row["eligible_for_compatible_timing"] for row in finding["organizer_offsets"])
    assert report["clips"][0]["reason_audit_failures"] == 1


def test_duplicate_timestamps_preserved_when_reason_is_compatible():
    report = evaluate(
        [label(4), label(47, t=68)],
        [prediction(OLD_CASH, 57)],
        assertions(observation(["X-4", "X-47"], OLD_CASH, "supported", [57, 57])),
    )
    summary, clip = report["summary"], report["clips"][0]
    assert summary["organizer_samples"] == 2
    assert summary["unique_sha_groups"] == summary["duplicate_samples"] == 1
    finding = clip["findings"][0]
    assert [f["timestamps_sec"] for f in clip["organizer_files"]] == [[57], [68]]
    assert finding["compatible_event_timing"][0]["absolute_distance_to_interval_sec"] == 0
    assert [row["signed_offsets_sec"] for row in finding["organizer_offsets"]] == [[0], [-11]]
    assert finding["legal_policy_status"] == "pending_source_review"


def test_combination_time_unknown_is_not_invented_from_organizer_marker():
    report = evaluate(
        [label(4)],
        [prediction("S-NO-MERGE")],
        assertions(observation(["X-4"], "S-NO-MERGE", "supported")),
    )
    timing = report["clips"][0]["findings"][0]["compatible_event_timing"][0]
    assert timing["human_interval_sec"] is None
    assert timing["absolute_distance_to_interval_sec"] is None


def test_wrong_exit_reason_is_failure_even_with_matching_verdict():
    report = evaluate(
        [label(20, t=5)],
        [prediction(LEAVE, 1)],
        assertions(observation(["X-20"], LEAVE, "contradicted")),
    )
    assert report["clips"][0]["unique_outcome"] == "TP"
    assert report["summary"]["finding_reason_counts"]["contradicted"] == 1


def test_unresolved_cause_has_no_reason_score_and_no_missing_cause_guess():
    report = evaluate(
        [label(1, t=22)],
        [prediction("C-REJECT-NOT-RETURNED", 22)],
        assertions(
            {
                "clip_ids": ["X-1"],
                "provenance_id": PROVENANCE["id"],
                "coverage": "partial",
                "cause_unresolved": True,
                "events": [],
                "reason_checks": [],
            }
        ),
    )
    assert report["summary"]["unknown_cause_sha_groups"] == 1
    finding = report["clips"][0]["findings"][0]
    assert finding["reason_status"] == "unknown"
    assert finding["compatible_event_timing"] == []
    assert "reason_accuracy" not in json.dumps(report)


def test_cutoff_blocks_future_abandonment_but_clean_twin_remains_clean():
    first, second = "a" * 64, "b" * 64
    report = evaluate(
        [label(43, first, False), label(45, second, False)],
        [prediction("L-NO-CASH-ON-LEAVE", sha=first), prediction(sha=second)],
        assertions(
            observation(["X-43"], "L-NO-CASH-ON-LEAVE", "contradicted", recording_cutoff=True),
            observation(["X-45"], "L-NO-CASH-ON-LEAVE", "contradicted", recording_cutoff=True),
        ),
    )
    counts = report["summary"]["unique_verdict_confusion"]
    assert counts["FP"] == counts["TN"] == 1
    assert report["summary"]["finding_reason_counts"]["contradicted"] == 1


def test_missing_predictions_are_missing_not_no_violation():
    report = evaluate([label(1), label(2, "b" * 64, False)], [])
    counts = report["summary"]["unique_verdict_confusion"]
    assert counts["missing"] == 2
    assert counts["FN"] == counts["TN"] == 0
    assert report["summary"]["missing_human_annotation_sha_groups"] == 2


@pytest.mark.parametrize(
    "raw",
    [
        {"sha256": "a" * 64},
        {"sha256": "a" * 64, "findings": None},
        {"sha256": "a" * 64, "findings": [None]},
        {"sha256": "a" * 64, "findings": [{"rule_id": "", "t": 3}]},
        {"sha256": "a" * 64, "findings": [{"rule_id": ID, "t": -1}]},
        {"sha256": "a" * 64, "findings": [{"rule_id": ID, "t": True}]},
        {"sha256": "a" * 64, "findings": [{"rule_id": ID, "t": float("nan")}]},
        {"sha256": "a" * 64, "findings": [{"rule_id": ID, "t": 10**400}]},
        {"sha256": "a" * 64, "findings": [{"rule_id": ID, "t": 101}]},
        {"sha256": "a" * 64, "findings": [], "verdict": "violation"},
        {"sha256": "a" * 64, "findings": [], "verdict": []},
        {"sha256": "a" * 64, "findings": [], "runtime_s": -3},
        {"sha256": "a" * 64, "findings": [], "wall_s": float("inf")},
        {"sha256": "a" * 64, "findings": [], "runtime_s": 8, "wall_s": 9},
        {"sha256": "a" * 64, "findings": [], "violations": []},
        {"sha256": "a" * 64, "findings": [], "status": "processing"},
    ],
)
def test_invalid_records_are_reported_and_excluded(raw):
    report = evaluate([label(1)], [raw])
    assert report["summary"]["unique_verdict_confusion"]["invalid"] == 1
    assert report["summary"]["invalid_output_records"] == 1
    assert report["summary"]["unique_verdict_confusion"]["FN"] == 0


def test_invalid_json_and_nonobject_records_do_not_prevent_remaining_audit():
    report = audit(
        json.dumps(label(1)),
        [({"path": "explicit.jsonl"}, "not JSON\n[]\n" + json.dumps(prediction()))],
        assertions(),
    )
    assert report["summary"]["invalid_output_records"] == 2
    assert report["summary"]["unique_verdict_confusion"]["FN"] == 1
    assert [error["record"] for error in report["invalid_outputs"]] == [1, 2]


def test_model_unavailable_is_failed_not_negative_and_does_not_leak_error_payload():
    raw = {"sha256": "a" * 64, "status": "failed", "error": "private-error-text", "runtime_s": 8}
    report = evaluate([label(1)], [raw])
    assert report["summary"]["unique_verdict_confusion"]["failed"] == 1
    assert report["summary"]["unique_verdict_confusion"]["FN"] == 0
    assert "private-error-text" not in json.dumps(report)


def test_occlusion_and_negative_stills_do_not_establish_id_non_presentation():
    observed = assertions(
        observation(
            ["X-19"], ID, "unknown", visibility="occluded_handover_and_sparse_negative_stills"
        )
    )
    report = evaluate([label(19, positive=False)], [prediction(ID)], observed)
    finding = report["clips"][0]["findings"][0]
    assert finding["reason_status"] == "unknown"
    assert finding["compatible_event_timing"] == []
    assert not finding["organizer_offsets"][0]["eligible_for_compatible_timing"]


def test_bad_clip_identity_is_rejected_without_copying_external_payload():
    raw = {**prediction(), "name": "PRIVATE-PAYLOAD-NOT-A-CLIP"}
    report = evaluate([label(1)], [raw])
    assert report["summary"]["invalid_output_records"] == 1
    assert report["invalid_outputs"][0]["error"] == "invalid clip identity"
    assert "PRIVATE-PAYLOAD" not in json.dumps(report)


def test_ranked_replay_uses_service_selected_findings():
    raw = {**prediction(ID), "ranked_findings": []}
    report = evaluate([label(1)], [raw])
    assert report["clips"][0]["findings_source"] == "ranked_findings"
    assert report["clips"][0]["unique_outcome"] == "FN"


def test_full_api_output_and_runtime_are_audited_without_copying_images():
    raw = {
        "sha256": "a" * 64,
        "status": "done",
        "verdict": "violation",
        "wall_s": 301,
        "violations": [
            {
                "rule_id": OLD_CASH,
                "timecode_sec": 57,
                "evidence_frames": [{"image_base64": "PRIVATE-IMAGE-PLACEHOLDER"}],
            }
        ],
    }
    report = evaluate([label(1)], [raw])
    assert report["clips"][0]["unique_outcome"] == "TP"
    assert report["summary"]["runtime"]["over_300_sec"] == 1
    assert report["summary"]["runtime"]["median_sec"] == 301
    assert "PRIVATE-IMAGE-PLACEHOLDER" not in json.dumps(report)


def test_repeated_api_results_count_one_sha_but_preserve_actual_runtime_records():
    first = {**prediction(ID), "runtime_s": 4}
    second = {**prediction(ID), "runtime_s": 8}
    report = evaluate([label(4), label(47, t=68)], [first, second])
    assert report["summary"]["unique_verdict_confusion"]["TP"] == 1
    assert report["summary"]["runtime"]["measured_records"] == 2
    assert report["summary"]["runtime"]["median_sec"] == 6
    assert len(report["clips"][0]["runtime_records"]) == 2


def test_conflicting_duplicate_predictions_are_rejected_without_last_record_wins():
    report = evaluate([label(4), label(47, t=68)], [prediction(ID), prediction()])
    assert report["clips"][0]["unique_outcome"] == "invalid"
    assert report["clips"][0]["findings"] == []
    assert any("conflicting" in error["error"] for error in report["invalid_outputs"])


def test_conflicting_duplicate_labels_are_not_assigned_a_unique_truth():
    report = evaluate([label(4), label(47, positive=False)], [prediction()])
    assert report["summary"]["unique_verdict_confusion"]["label_conflict"] == 1
    assert report["summary"]["sample_verdict_confusion"]["FN"] == 1
    assert report["summary"]["sample_verdict_confusion"]["TN"] == 1


def test_unlabelled_prediction_does_not_expand_the_evaluation_set():
    report = evaluate([label(1)], [prediction(sha="b" * 64)])
    assert report["summary"]["unlabelled_prediction_records"] == 1
    assert report["summary"]["unique_verdict_confusion"]["missing"] == 1


def test_clip_and_sha_must_agree():
    raw = {**prediction(sha="b" * 64), "name": "X-1.mov"}
    report = evaluate([label(1)], [raw])
    assert report["summary"]["invalid_output_records"] == 1
    assert report["invalid_outputs"][0]["error"] == "prediction clip and SHA disagree"


def test_assertions_require_provenance_and_cannot_combine_different_sha_groups():
    bad = assertions(observation(["X-1", "X-2"], ID, "unknown"))
    with pytest.raises(ValueError, match="one SHA"):
        evaluate([label(1), label(2, "b" * 64)], [], bad)
    bad = assertions(observation(["X-1"], ID, "unknown"))
    bad["clips"][0]["provenance_id"] = "another-source"
    with pytest.raises(ValueError, match="provenance"):
        evaluate([label(1)], [], bad)


def test_provisional_id_policy_is_preserved_without_becoming_reason_truth():
    observed = assertions(observation(["X-19"], ID, "unknown"))
    observed["rule_assumptions"] = [{"id": "physical-id-first", "status": "provisional_policy"}]
    report = evaluate([label(19, positive=False)], [prediction(ID)], observed)
    assert report["summary"]["unique_verdict_confusion"]["FP"] == 1
    assert report["clips"][0]["findings"][0]["reason_status"] == "unknown"
    assert report["rule_assumptions"][0]["status"] == "provisional_policy"


@pytest.fixture
def pinned(tmp_path: Path):
    labels_path, predictions_path, assertions_path = (
        tmp_path / "labels.jsonl",
        tmp_path / "predictions.jsonl",
        tmp_path / "assertions.json",
    )
    dump_json(labels_path, label(1))
    dump_json(predictions_path, prediction())
    dump_json(assertions_path, assertions())
    manifest = make_manifest(labels_path, [predictions_path], assertions_path, tmp_path)
    manifest_path = tmp_path / "inputs.json"
    dump_json(manifest_path, manifest)
    return tmp_path, manifest_path, manifest


@pytest.mark.parametrize("which", ["labels", "predictions", "assertions"])
def test_pin_mismatch_fails_closed_even_for_whitespace_change(pinned, which):
    root, path, manifest = pinned
    entry = manifest[which][0] if which == "predictions" else manifest[which]
    source = root / entry["path"]
    source.write_text(source.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_manifest(path, root)


def test_reference_source_hash_is_pinned_too(pinned):
    root, path, manifest = pinned
    source = root / "rules.py"
    source.write_text("# old reference\n", encoding="utf-8")
    from eval.audit_findings import pin_file

    manifest["references"] = [pin_file(source, root)]
    dump_json(path, manifest)
    source.write_text("# changed reference\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_manifest(path, root)


def test_newer_unlisted_cache_is_never_selected(pinned):
    root, path, _ = pinned
    dump_json(root / "newer-unlisted.jsonl", prediction(ID))
    report = run_manifest(path, root)
    assert report["clips"][0]["unique_outcome"] == "FN"
    assert len(report["inputs"]["predictions"]) == 1


def test_cli_pin_and_run_create_reviewable_artifacts(pinned, capsys):
    root, _, _ = pinned
    manifest_path, output, md = root / "cli-inputs.json", root / "audit.json", root / "audit.md"
    assert (
        main(
            [
                "pin",
                "--root",
                str(root),
                "--labels",
                str(root / "labels.jsonl"),
                "--predictions",
                str(root / "predictions.jsonl"),
                "--assertions",
                str(root / "assertions.json"),
                "--out",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "run",
                "--root",
                str(root),
                "--manifest",
                str(manifest_path),
                "--out",
                str(output),
                "--markdown",
                str(md),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["summary"]["unique_verdict_confusion"]["FN"] == 1
    assert "Independent findings audit" in md.read_text()
    assert '"unique_sha_groups": 1' in capsys.readouterr().out


def test_full_api_identity_can_be_explicit_in_manifest(pinned):
    root, path, manifest = pinned
    raw = {"status": "done", "verdict": "no_violation", "violations": []}
    dump_json(root / "api.json", raw)
    from eval.audit_findings import pin_file

    manifest["predictions"] = [{**pin_file(root / "api.json", root), "clip_id": "X-1"}]
    dump_json(path, manifest)
    report = run_manifest(path, root)
    assert report["clips"][0]["findings_source"] == "violations"
    assert report["clips"][0]["unique_outcome"] == "FN"


def test_failed_pin_returns_nonzero_and_does_not_write_report(pinned, capsys):
    root, path, _ = pinned
    (root / "predictions.jsonl").write_text("changed", encoding="utf-8")
    output = root / "should-not-exist.json"
    assert main(["run", "--root", str(root), "--manifest", str(path), "--out", str(output)]) == 2
    assert not output.exists()
    assert "audit failed" in capsys.readouterr().err


def test_invalid_assertion_status_and_interval_fail_explicitly():
    observed = assertions(observation(["X-1"], ID, "invented"))
    with pytest.raises(ValueError, match="status"):
        evaluate([label(1)], [], observed)
    observed = assertions(observation(["X-1"], ID, "unknown", [57, 55]))
    with pytest.raises(ValueError, match="interval"):
        evaluate([label(1)], [], observed)


def test_unknown_cause_with_missing_prediction_is_still_unknown_not_false_negative_reason():
    observed = assertions(
        {
            "clip_ids": ["X-1"],
            "provenance_id": PROVENANCE["id"],
            "cause_unresolved": True,
            "events": [],
            "reason_checks": [],
        }
    )
    report = evaluate([label(1)], [], observed)
    assert report["summary"]["unknown_cause_sha_groups"] == 1
    assert report["summary"]["finding_reason_counts"] == {
        "contradicted": 0,
        "supported": 0,
        "unknown": 0,
    }


def test_input_objects_are_not_mutated():
    labels, predictions = [label(1)], [prediction(ID)]
    observed = assertions(observation(["X-1"], ID, "unknown"))
    saved = deepcopy((labels, predictions, observed))
    evaluate(labels, predictions, observed)
    assert (labels, predictions, observed) == saved
