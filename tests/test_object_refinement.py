"""Offline crop geometry and evaluation failure semantics; no model results are mocked as real."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.config import ROOT
from backend.f1.object_refinement import SourceCrop, native_tiles, remap_detections
from backend.f1.vision_types import Detection


@pytest.fixture(scope="module")
def probe():
    path = ROOT / "attempts/A21-deadline/recognition/compare_objects.py"
    spec = importlib.util.spec_from_file_location("a21_object_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("size", [(464, 848), (848, 464), (1920, 1080), (97, 113), (640, 640)])
def test_native_tiles_cover_every_axis_and_reach_edges(size):
    width, height = size
    tiles = native_tiles(width, height)
    assert len({tile.bounds for tile in tiles}) == len(tiles)
    for tile in tiles:
        tile.validate(width, height)
        assert max(tile.size) <= 640
    for axis, length in enumerate(size):
        intervals = sorted({(tile.bounds[axis], tile.bounds[axis + 2]) for tile in tiles})
        assert intervals[0][0] == 0
        assert intervals[-1][1] == length
        assert all(
            end >= start for (_, end), (start, _) in zip(intervals, intervals[1:], strict=False)
        )


def test_overlapping_tiles_are_independent_of_orientation_and_labels():
    portrait = native_tiles(464, 848)
    landscape = native_tiles(848, 464)
    assert [c.bounds for c in portrait] == [(0, 0, 464, 640), (0, 208, 464, 848)]
    assert {c.bounds for c in landscape} == {(c.top, c.left, c.bottom, c.right) for c in portrait}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 0},
        {"height": -1},
        {"width": True},
        {"height": 2.5},
        {"tile_size": 0},
        {"tile_size": 16.0},
        {"overlap": -0.1},
        {"overlap": 1},
        {"overlap": float("nan")},
        {"overlap": float("inf")},
    ],
)
def test_tile_geometry_rejects_invalid_inputs(kwargs):
    values = {"width": 100, "height": 200, **kwargs}
    with pytest.raises(ValueError):
        native_tiles(**values)


def test_crop_remapping_uses_both_native_axes_and_does_not_mutate_input():
    crop = SourceCrop(100, 200, 500, 800)
    original = Detection(label="cash", score=0.8, box=(0.25, 0.25, 0.75, 0.75))
    mapped = remap_detections([original], crop, 1000, 1000)
    assert mapped[0].box == pytest.approx((0.2, 0.35, 0.4, 0.65))
    assert original.box == (0.25, 0.25, 0.75, 0.75)
    assert mapped[0] is not original


def test_installed_owlv2_postprocessor_already_accounts_for_square_padding():
    import torch
    from transformers import Owlv2ImageProcessor

    from backend.f1.perception import normal_box

    # The real crop is 464 x 640; OWLv2 pads its right side to 640 before resizing.
    # Supply a box which should occupy x=[.1,.3], y=[.2,.4] in the unpadded crop.
    raw = SimpleNamespace(
        logits=torch.tensor([[[10.0]]]),
        pred_boxes=torch.tensor([[[0.2 * 464 / 640, 0.3, 0.2 * 464 / 640, 0.2]]]),
    )
    result = Owlv2ImageProcessor().post_process_object_detection(
        raw, threshold=0.12, target_sizes=[(640, 464)]
    )[0]
    crop_box = normal_box(result["boxes"][0].numpy(), 464, 640)
    assert crop_box == pytest.approx((0.1, 0.2, 0.3, 0.4))
    mapped = SourceCrop(0, 208, 464, 848).remap(crop_box, 464, 848)
    assert mapped == pytest.approx((0.1, (208 + 128) / 848, 0.3, (208 + 256) / 848))


@pytest.mark.parametrize(
    "box",
    [
        (-0.1, 0, 1, 1),
        (0, 0, 1.1, 1),
        (0, 0, 0, 1),
        (0.5, 0, 0.3, 1),
        (0, float("nan"), 1, 1),
        (0, 0, float("inf"), 1),
    ],
)
def test_remapping_rejects_invalid_model_boxes(box):
    with pytest.raises(ValueError):
        SourceCrop(0, 0, 100, 100).remap(box, 100, 100)


@pytest.mark.parametrize(
    "crop",
    [
        SourceCrop(-1, 0, 10, 10),
        SourceCrop(0, 0, 101, 10),
        SourceCrop(10, 0, 5, 10),
        SourceCrop(0.0, 0, 10, 10),
    ],
)
def test_remapping_rejects_invalid_crop_bounds(crop):
    with pytest.raises(ValueError):
        crop.remap((0, 0, 1, 1), 100, 100)


def crop_result(*labels, ok=True):
    return {
        "name": "test_crop",
        "ok": ok,
        "sec": 0.1,
        "detections": [
            Detection(label=label, score=0.8, box=(0.1, 0.2, 0.3, 0.4)).model_dump()
            for label in labels
        ],
    }


def test_full_frame_truth_applies_to_crop_union_not_each_crop(probe):
    result = probe.union_prediction([crop_result(), crop_result("cash")])
    assert result["pred"]["cash"] is True
    assert result["pred"]["id_card"] is False
    record = {"expected": {"cash": True}, "variants": {v: result for v in probe.VARIANTS}}
    cash = probe.summarise([record])["native_tiles"]["classes"]["cash"]
    assert cash["tp"] == 1
    assert cash["fn"] == 0


def test_clean_twin_id_phone_and_document_are_not_cash(probe):
    positive = probe.union_prediction([crop_result("bundle", "id_card")])
    clean = probe.union_prediction([crop_result("phone", "id_card", "document")])
    assert positive["pred"]["cash"] is True
    assert clean["pred"]["cash"] is False
    assert clean["pred"]["id_card"] is True


def test_failed_or_unavailable_crops_are_unknown_unless_another_crop_is_positive(probe):
    failed = crop_result(ok=False)
    assert probe.union_prediction([])["pred"]["cash"] is None
    assert probe.union_prediction([failed, crop_result()])["pred"]["cash"] is None
    result = probe.union_prediction([failed, crop_result("cash")])
    assert result["pred"]["cash"] is True
    assert result["pred"]["id_card"] is None
    assert not result["ok"]
    assert result["failed_crops"] == 1


def test_unlabelled_is_distinct_from_negative_and_unknown_from_missed(probe):
    def record(truth, crops):
        result = probe.union_prediction(crops)
        return {"expected": truth, "variants": {v: result for v in probe.VARIANTS}}

    summary = probe.summarise(
        [
            record({"cash": True}, [crop_result("cash")]),
            record({"cash": False}, [crop_result("cash")]),
            record({"cash": True}, [crop_result()]),
            record({"cash": False}, [crop_result()]),
            record({"cash": True}, [crop_result(ok=False)]),
            record({"cash": False}, [crop_result(ok=False)]),
            record({"id_card": True}, [crop_result("cash")]),
        ]
    )
    assert summary["full_desk"]["classes"]["cash"] == {
        "tp": 1,
        "fp": 1,
        "fn": 1,
        "tn": 1,
        "unknown": 2,
        "unknown_positive": 1,
        "unknown_negative": 1,
        "unlabelled": 1,
    }


def test_inference_failure_and_invalid_output_are_recorded_as_unknown(probe):
    def unavailable(*_args):
        raise RuntimeError("test unavailable")

    fake = SimpleNamespace(objects=unavailable)
    result = probe.run_crop(fake, Image.new("RGB", (32, 48)), SourceCrop(0, 0, 32, 48), {}, "full")
    assert not result["ok"]
    assert result["error_type"] == "RuntimeError"
    assert result["error"] == "test unavailable"
    assert probe.union_prediction([result])["pred"]["cash"] is None

    def invalid_output(*_args):
        fake.last_invalid_output_values = 3
        return []

    fake.objects, fake.sync = invalid_output, lambda: None
    result = probe.run_crop(fake, Image.new("RGB", (32, 48)), SourceCrop(0, 0, 32, 48), {}, "full")
    assert not result["ok"]
    assert result["invalid_output_values"] == 3
    assert probe.union_prediction([result])["pred"]["cash"] is None


def test_recording_cutoff_is_not_replaced_by_nearest_available_frame(probe, monkeypatch):
    import cv2

    calls = []
    fake = SimpleNamespace(
        isOpened=lambda: True,
        get=lambda key: {cv2.CAP_PROP_FPS: 10.0, cv2.CAP_PROP_FRAME_COUNT: 20}[key],
        release=lambda: calls.append("release"),
        set=lambda *_: calls.append("seek"),
        read=lambda: calls.append("read"),
    )
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: fake)
    with pytest.raises(ValueError, match="outside the recording"):
        probe.grab_frame(Path("synthetic.mov"), 2.0)
    assert calls == ["release"]


def test_a13_labels_are_loaded_without_executing_original_probe(probe):
    cases = probe.read_cases(ROOT / "attempts/A13-detection-spike/scripts/spike_test.py")
    assert len(cases) == 20
    assert sum(c["expected"].get("cash") is True for c in cases) == 7
    assert sum(c["expected"].get("cash") is False for c in cases) == 4
    assert sum(c["expected"].get("id_card") is True for c in cases) == 1
    assert sum(c["expected"].get("id_card") is False for c in cases) == 1


def test_unavailable_model_writes_all_unknowns_and_nonzero_exit(probe, monkeypatch, tmp_path):
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "manifest.json").write_text(json.dumps({"models": [{"name": "objects"}]}))
    monkeypatch.setattr(probe, "verify_weights", lambda _: "test_manifest")

    def unavailable(*_args):
        raise RuntimeError("test: offline checkpoint unavailable")

    monkeypatch.setattr(probe, "OwlProbe", unavailable)
    output = tmp_path / "output"
    assert (
        probe.main(
            [
                "--videos",
                str(tmp_path),
                "--weights",
                str(weights),
                "--out",
                str(output),
                "--device",
                "cpu",
            ]
        )
        == 2
    )
    assert json.loads((output / "metadata.json").read_text())["status"] == "model_unavailable"
    cash = json.loads((output / "summary.json").read_text())["full_desk"]["classes"]["cash"]
    assert cash["unknown"] == 11
    assert cash["unknown_positive"] == 7
    assert cash["unknown_negative"] == 4
    assert cash["fn"] == cash["tn"] == cash["tp"] == cash["fp"] == 0


def test_real_offline_loader_rejects_missing_checkpoint_without_negative_predictions(
    probe, tmp_path
):
    # Use the real Transformers loader and an empty local directory, without a video.
    # This tests checkpoint failure only and is not inference or a recognition result.
    (tmp_path / "objects").mkdir()
    with pytest.raises(OSError):
        probe.OwlProbe(tmp_path, "cpu", 1, {"owl_image_size": 640, "object_score": 0.12})
