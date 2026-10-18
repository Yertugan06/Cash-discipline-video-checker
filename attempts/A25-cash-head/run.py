#!/usr/bin/env python3
"""A25 train-only regularization selection; A24 stays read-only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

os.environ.update(CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
sys.dont_write_bytecode = True
import numpy as np

GRID = [0.0001, 0.001, 0.01, 0.1]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()}


def write(path, value):
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    temporary.replace(path)


def fit_lambda(module, features, labels, groups, value):
    # A24's API hardcodes lambda; change only the isolated module value, never its source.
    original = module.LAMBDA
    try:
        module.LAMBDA = value
        return module.fit(features, labels, groups)
    finally:
        module.LAMBDA = original


def selfcheck(module):
    x = np.array([[1., 0., 0.], [-1., 0., 0.]])
    expected = module.fit(x, [1, 0], ["positive", "negative"])
    same = fit_lambda(module, x, [1, 0], ["positive", "negative"], 0.1)
    assert np.allclose(same["coefficients"], expected["coefficients"])
    head = json.loads(json.dumps(fit_lambda(module, x, [1, 0], ["positive", "negative"], 0.01), allow_nan=False))
    assert [module.predict(f, head)["state"] for f in x] == ["present", "not_detected"]
    assert module.predict([0., 0., 1.], head)["state"] == "unknown"
    assert module.LAMBDA == 0.1 and head["lambda"] == 0.01


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("a24", "base", "cache", "videos", "model", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    before = snapshot(args.a24)
    write(args.out / "a24-before.json", before)
    sys.path.insert(0, str(args.a24.resolve()))
    import model as a24_model
    import train as a24_train
    assert Path(a24_model.__file__).parent == args.a24.resolve()
    selfcheck(a24_model)
    old = json.loads((args.a24 / "artifacts/run-01/report.json").read_text())
    head = json.loads((args.a24 / "artifacts/run-01/head.json").read_text())
    labels_path = args.a24 / "artifacts/run-01/label-manifest.used.json"
    manifest = json.loads(labels_path.read_text())["records"]
    assert digest(labels_path) == old["labels_sha256"] == head["labels_sha256"]
    assert digest(args.a24 / "train.py") == old["runner_sha256"]
    assert digest(args.a24 / "model.py") == head["head_code_sha256"] == old["head_code_sha256"]
    assert digest(args.a24 / "artifacts/run-01/head.json") == old["head_sha256"]
    source = (args.a24 / "train.py").read_text()
    assert "for flip in (False, True) for brightness in (0.9, 1.0, 1.1)" in source
    assert "if not flip and brightness == 1.0" in source
    assert "train_features.extend(f for _, _, f in row_features)" in source
    train = [(i, row) for i, row in enumerate(manifest) if row["split"] == "train"]
    assert len(train) == 8 and old["training_augmented_samples"] == 48
    features = np.asarray(head["train_reference_features"], dtype=float)
    assert features.shape == (48, 3840) and np.isfinite(features).all()
    groups = np.repeat([r["group_sha256"] for _, r in train], 6)
    targets = np.repeat([int(r["cash_visible"]) for _, r in train], 6)
    probe_hashes = {r["group_sha256"] for r in manifest if r["split"] == "probe"}
    assert len(set(groups)) == 8 and not set(groups) & probe_hashes
    proof = []
    for position, (index, row) in enumerate(train):
        prior = old["rows"][index]
        assert prior["index"] == index and prior["source_sha256"] == row["video_sha256"]
        assert prior["augmentations"] == 6 and prior["status"] == "features_ready"
        score = a24_model.predict(features[position*6+1], head)["score"]
        assert abs(score-prior["score"]) < 1e-8
        proof.append({"row_index": index, "group_sha256": row["group_sha256"],
                      "identity_offset": position*6+1, "reproduced_a24_score_delta": score-prior["score"]})
    selection = {"status": "selecting_train_only", "grid": GRID, "candidates": [], "ordering_proof": proof,
        "a24_source_sha256": {name: before[name] for name in ("train.py", "model.py", "PREREGISTER.md")},
        "a24_head_sha256": old["head_sha256"], "feature_cache_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "labels_sha256": old["labels_sha256"], "preregister_sha256": digest(Path(__file__).with_name("PREREGISTER.md")),
        "probe_used_for_selection": False, "selfcheck": "passed"}
    for value in GRID:
        folds = []
        for position, (index, row) in enumerate(train):
            held = row["group_sha256"]
            keep = groups != held
            assert int(keep.sum()) == 42 and not np.any(groups[keep] == held)
            fitted = fit_lambda(a24_model, features[keep], targets[keep], groups[keep].tolist(), value)
            score = a24_model.predict(features[position*6+1], fitted)["score"]
            target = 2*int(row["cash_visible"])-1
            folds.append({"row_index": index, "group_sha256": held, "label": int(row["cash_visible"]),
                          "score": score, "squared_error": (score-target)**2,
                          "fit_samples": int(keep.sum()), "omitted_augmentations": 6})
        balanced = 0.5*sum(float(np.mean([f["squared_error"] for f in folds if f["label"] == label]))
                           for label in (0, 1))
        selection["candidates"].append({"lambda": value, "class_balanced_loco_mse": balanced, "folds": folds})
    chosen = min(selection["candidates"], key=lambda r: (r["class_balanced_loco_mse"], -r["lambda"]))["lambda"]
    selection.update(status="selected_before_probe_extraction", selected_lambda=chosen,
                     selection_elapsed_sec=time.monotonic()-started)
    write(args.out / "selection.json", selection)
    print(json.dumps({"status": selection["status"], "lambda": chosen,
                      "candidate_losses": [{k: r[k] for k in ("lambda", "class_balanced_loco_mse")}
                                           for r in selection["candidates"]]}), flush=True)
    final = fit_lambda(a24_model, features, targets, groups.tolist(), chosen)
    for key in ("backbone_pin", "preprocess", "source_sha256", "labels_sha256", "score_semantics"):
        final[key] = head[key]
    final.update(attempt="A25", selection_sha256=digest(args.out / "selection.json"),
                 a24_head_sha256=old["head_sha256"], feature_cache_sha256=selection["feature_cache_sha256"],
                 runner_sha256=digest(Path(__file__)), preregister_sha256=selection["preregister_sha256"])
    write(args.out / "head.json", final)
    final = json.loads((args.out / "head.json").read_text())
    report = {"status": "extracting_probe_after_selection", "selected_lambda": chosen,
        "a24_confusion": old["confusion"], "rows": [], "probe_used_for_fit_or_selection": False,
        "probe_augmented": False, "score_kind": "uncalibrated_signed_ridge",
        "all_public_40_influenced_development": True, "a24_probe_already_seen": True,
        "new_heldout_accuracy_claim": False, "device": "cpu", "threads": 2}
    for position, (index, row) in enumerate(train):
        report["rows"].append({"index": index, "clip": row["clip"], "split": "train", "label": int(row["cash_visible"]),
                              **a24_model.predict(features[position*6+1], final)})
    write(args.out / "report.json", report)
    sys.path.insert(0, str(args.base.resolve()))
    from backend.f1.vision_types import Scene
    import cv2
    from PIL import Image, ImageEnhance, ImageOps
    import torch
    from transformers import AutoModel, AutoImageProcessor
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    cv2.setNumThreads(2)
    for item in final["backbone_pin"]["files"]:
        assert digest(args.model / item["path"]) == item["sha256"]
    backbone = AutoModel.from_pretrained(args.model, local_files_only=True, use_safetensors=True,
                                         dtype=torch.float32).eval().to("cpu")
    backbone.requires_grad_(False)
    processor = AutoImageProcessor.from_pretrained(args.model, local_files_only=True)
    files = {p.stem.replace("Х", "X"): p for p in args.videos.iterdir() if p.is_file()}
    for index, row in enumerate(manifest):
        if row["split"] != "probe":
            continue
        record = {"index": index, "clip": row["clip"], "split": "probe", "label": int(row["cash_visible"])}
        try:
            video = files[row["clip"]]
            assert digest(video) == row["video_sha256"]
            candidates = list((args.cache / row["video_sha256"]).glob("*.json"))
            assert len(candidates) == 1 and digest(candidates[0]) == old["rows"][index]["cache_sha256"]
            scene = Scene.model_validate(json.loads(candidates[0].read_text())["scene"])
            box = a24_train.roi_box(scene)
            capture = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2])
            try:
                capture.set(cv2.CAP_PROP_POS_MSEC, row["t"]*1000)
                ok, pixels = capture.read()
                actual = float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000
            finally:
                capture.release()
            if not ok or not math.isfinite(actual) or abs(actual-row["t"]) > 0.12:
                raise ValueError("actual_decode_time_mismatch")
            height, width = pixels.shape[:2]
            bounds = [math.floor(box[0]*width), math.floor(box[1]*height),
                      math.ceil(box[2]*width), math.ceil(box[3]*height)]
            assert bounds == old["rows"][index]["roi_pixels"]
            image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)).crop(bounds)
            image = ImageEnhance.Brightness(image).enhance(1.0)
            scaled = ImageOps.contain(image, (224, 224), Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (224, 224), (124, 116, 104))
            canvas.paste(scaled, ((224-scaled.width)//2, (224-scaled.height)//2))
            inputs = processor(images=canvas, do_resize=False, do_center_crop=False, return_tensors="pt")
            with torch.inference_mode():
                hidden = backbone(**inputs).last_hidden_state
                assert tuple(hidden.shape) == (1, 257, 768)
                grid = hidden[:, 1:].reshape(1, 16, 16, 768)
                parts = [hidden[:, 0]] + [grid[:, a:a+8, b:b+8].mean(dim=(1, 2)) for a in (0, 8) for b in (0, 8)]
                feature = torch.cat([torch.nn.functional.normalize(p, dim=1) for p in parts], dim=1)
                feature = torch.nn.functional.normalize(feature, dim=1)[0].numpy().copy()
            old_score = a24_model.predict(feature, head)["score"]
            assert abs(old_score-old["rows"][index]["score"]) < 1e-5
            record.update(requested_t=row["t"], actual_t=actual, roi_box=box, roi_pixels=bounds,
                          reextracted_a24_score_delta=old_score-old["rows"][index]["score"],
                          **a24_model.predict(feature, final))
        except (ValueError, OSError) as exc:
            record.update(state="unknown", reason=str(exc)[:300])
        report["rows"].append(record)
        write(args.out / "report.json", report)
    assert snapshot(args.a24) == before, "A24 changed; preserve original bytes"
    report.update(status="trained", elapsed_sec=time.monotonic()-started, a24_byte_identical=True,
        head_sha256=digest(args.out / "head.json"), selection_sha256=digest(args.out / "selection.json"),
        confusion={split: a24_train.confusion([r for r in report["rows"] if r["split"] == split])
                   for split in ("train", "probe")})
    write(args.out / "report.json", report)
    print(json.dumps({k: report[k] for k in ("status", "selected_lambda", "elapsed_sec", "confusion", "a24_byte_identical")}))


if __name__ == "__main__":
    main()
