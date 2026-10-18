#!/usr/bin/env python3
"""A24 own region-presence training. CPU/offline; exports only JSON numbers/text."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

# Set before NumPy/Torch imports so this CPU job cannot compete for GPU memory.
os.environ.update(CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
import numpy as np
from model import fit, predict


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    temporary.replace(path)


def roi_box(scene):
    def box(name):
        item = scene.objects.get(name)
        if item is None:
            return None
        x1, y1, x2, y2 = item.box
        if not np.isfinite(item.box).all() or not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("invalid_calibrated_" + name)
        return x1, y1, x2, y2
    desk, counter = box("desk"), box("counter")
    if desk is None:
        raise ValueError("missing_calibrated_desk")
    x1, y1, x2, y2 = desk
    dx, dy = (x2-x1)*0.1, (y2-y1)*0.1
    result = [max(0, x1-dx), max(0, y1-dy), min(1, x2+dx), min(1, y2+dy)]
    if counter is not None:
        result = [min(result[0], counter[0]), min(result[1], counter[1]),
                  max(result[2], counter[2]), max(result[3], counter[3])]
    return result


def load_rows(path):
    manifest = json.loads(path.read_text())
    rows = manifest.get("records", manifest.get("rows", manifest.get("samples", manifest.get("cases"))))
    if not isinstance(rows, list):
        raise ValueError("manifest needs rows list")
    if len(rows) != 12:
        raise ValueError("preregistered 12 reviewed source rows required")
    for row in rows:
        if "cash_visible" in row:
            row["label"] = row["cash_visible"]
        if row.get("split") not in ("train", "probe") or row.get("label") not in (0, 1, False, True):
            raise ValueError("explicit train/probe split and binary human label required")
    if sum(r["split"] == "train" for r in rows) != 8 or sum(r["split"] == "probe" for r in rows) != 4:
        raise ValueError("preregistered split must be eight train/four probe")
    return manifest, rows


def confusion(rows):
    counts = {k: 0 for k in ("tp", "tn", "fp", "fn", "unknown_positive", "unknown_negative")}
    for row in rows:
        positive = bool(row["label"])
        if row["state"] == "unknown":
            key = "unknown_positive" if positive else "unknown_negative"
        elif row["state"] == "present":
            key = "tp" if positive else "fp"
        else:
            key = "fn" if positive else "tn"
        counts[key] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("base", "cache", "videos", "labels", "model", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--device", choices=["cpu"], default="cpu")
    parser.add_argument("--threads", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {"status": "initializing", "device": "cpu", "threads": args.threads,
              "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"], "rows": [],
              "all_public_40_influenced_development": True, "held_out_accuracy_claim": False,
              "score_kind": "uncalibrated_signed_ridge", "source_base": str(args.base),
              "runner_sha256": digest(Path(__file__)), "head_code_sha256": digest(Path(__file__).with_name("model.py")),
              "preregister_sha256": digest(Path(__file__).with_name("PREREGISTER.md"))}
    def checkpoint():
        report["elapsed_sec"] = time.monotonic()-started
        write(args.out / "report.json", report)
    checkpoint()
    try:
        manifest, rows = load_rows(args.labels)
        report["labels_sha256"] = digest(args.labels)
        sys.path.insert(0, str(args.base.resolve()))
        from backend.f1.vision_types import Scene
        import cv2
        from PIL import Image, ImageEnhance, ImageOps
        import torch
        import transformers
        from transformers import AutoImageProcessor, AutoModel
        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(args.threads)
        cv2.setNumThreads(args.threads)
        assert os.environ["CUDA_VISIBLE_DEVICES"] == ""
        report.update(torch=torch.__version__, transformers=transformers.__version__)
        download = json.loads((args.model / "download-manifest.json").read_text())
        if download["status"] != "ready" or download["repo_id"] != "facebook/dinov2-base":
            raise ValueError("backbone download not ready/pinned")
        for item in download["files"]:
            if digest(args.model / item["path"]) != item["sha256"]:
                raise ValueError("backbone hash mismatch: " + item["path"])
        report["backbone"] = download
        report["source_sha256"] = {name: digest(args.base / name) for name in (
            "backend/f1/vision_types.py", "backend/f1/calibration.py")}
        index = [json.loads(s) for s in (args.base / "data/prepared/videos.jsonl").read_text().splitlines() if s]
        files = {p.stem.replace("Х", "X"): p for p in args.videos.iterdir() if p.is_file()}
        resolved = []
        for i, row in enumerate(rows):
            sha = row.get("video_sha256", row.get("source_sha256", row.get("sha256")))
            if not sha:
                raise ValueError("every row needs pinned video SHA")
            entry = next(e for e in index if e["sha256"] == sha)
            video = files[entry["original_id"].replace("Х", "X")]
            if digest(video) != sha:
                raise ValueError("video hash mismatch")
            candidates = list((args.cache / sha).glob("*.json"))
            if row.get("cache_path"):
                cache = Path(row["cache_path"])
            elif len(candidates) == 1:
                cache = candidates[0]
            else:
                raise ValueError("need one explicitly pinned cache; no newest-mtime choice")
            cache_sha = digest(cache)
            if row.get("cache_sha256") and cache_sha != row["cache_sha256"]:
                raise ValueError("cache hash mismatch")
            requested = row.get("t", row.get("time_sec", row.get("timestamp_sec")))
            if requested is None or not math.isfinite(requested) or requested < 0:
                raise ValueError("finite explicit frame time required")
            resolved.append({"index": i, "split": row["split"], "label": int(row["label"]),
                "source_sha256": sha, "parent_sha256": row.get("parent_sha256", row.get("group_sha256", sha)),
                "requested_t": requested, "video": video, "cache": cache, "cache_sha256": cache_sha})
        train_hashes = {r["source_sha256"] for r in resolved if r["split"] == "train"}
        probe_hashes = {r["source_sha256"] for r in resolved if r["split"] == "probe"}
        train_parents = {r["parent_sha256"] for r in resolved if r["split"] == "train"}
        probe_parents = {r["parent_sha256"] for r in resolved if r["split"] == "probe"}
        if train_hashes & probe_hashes or train_parents & probe_parents:
            raise ValueError("source/parent clip leakage across train/probe")
        report.update(status="loading_cpu_backbone", train_group_hashes=sorted(train_hashes),
                      probe_group_hashes=sorted(probe_hashes))
        checkpoint()
        model_started = time.monotonic()
        backbone = AutoModel.from_pretrained(args.model, local_files_only=True,
            use_safetensors=True, dtype=torch.float32).eval().to("cpu")
        backbone.requires_grad_(False)
        processor = AutoImageProcessor.from_pretrained(args.model, local_files_only=True)
        assert next(backbone.parameters()).device.type == "cpu"
        assert next(backbone.parameters()).dtype == torch.float32
        report["model_load_sec"] = time.monotonic()-model_started
        report["preprocess"] = {"roi": "desk_expanded_10pct_each_side_union_counter", "size": [224, 224],
            "letterbox_rgb": [124, 116, 104], "resize": "bilinear", "do_resize": False,
            "do_center_crop": False, "features": "CLS+four_quadrant_means_each_l2_concat_l2", "dimension": 3840}
        train_features, train_labels, train_groups = [], [], []
        identity_features = {}
        for row in resolved:
            record = {k: v for k, v in row.items() if k not in ("video", "cache")}
            report["rows"].append(record)
            report["status"] = "extracting_cpu_features"
            checkpoint()
            row_started = time.monotonic()
            try:
                scene = Scene.model_validate(json.loads(row["cache"].read_text())["scene"])
                box = roi_box(scene)
                capture = cv2.VideoCapture(str(row["video"]), cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_N_THREADS, args.threads])
                try:
                    capture.set(cv2.CAP_PROP_POS_MSEC, row["requested_t"]*1000)
                    ok, pixels = capture.read()
                    actual = float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000
                finally:
                    capture.release()
                if not ok or not math.isfinite(actual) or abs(actual-row["requested_t"]) > 0.12:
                    raise ValueError("actual_decode_time_mismatch")
                height, width = pixels.shape[:2]
                bounds = [math.floor(box[0]*width), math.floor(box[1]*height),
                          math.ceil(box[2]*width), math.ceil(box[3]*height)]
                image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)).crop(bounds)
                record.update(actual_t=actual, native_size=[width, height], roi_box=box,
                              roi_pixels=bounds, native_crop_size=list(image.size))
                variants = [(False, 1.0)] if row["split"] == "probe" else [
                    (flip, brightness) for flip in (False, True) for brightness in (0.9, 1.0, 1.1)]
                row_features = []
                for flip, brightness in variants:
                    variant = ImageOps.mirror(image) if flip else image
                    variant = ImageEnhance.Brightness(variant).enhance(brightness)
                    scaled = ImageOps.contain(variant, (224, 224), Image.Resampling.BILINEAR)
                    canvas = Image.new("RGB", (224, 224), (124, 116, 104))
                    canvas.paste(scaled, ((224-scaled.width)//2, (224-scaled.height)//2))
                    inputs = processor(images=canvas, do_resize=False, do_center_crop=False, return_tensors="pt")
                    assert tuple(inputs["pixel_values"].shape) == (1, 3, 224, 224)
                    with torch.inference_mode():
                        hidden = backbone(**inputs).last_hidden_state
                        assert tuple(hidden.shape) == (1, 257, 768)
                        grid = hidden[:, 1:].reshape(1, 16, 16, 768)
                        parts = [hidden[:, 0]] + [grid[:, a:a+8, b:b+8].mean(dim=(1, 2))
                                                  for a in (0, 8) for b in (0, 8)]
                        feature = torch.cat([torch.nn.functional.normalize(p, dim=1) for p in parts], dim=1)
                        feature = torch.nn.functional.normalize(feature, dim=1)[0].numpy().copy()
                    if feature.shape != (3840,) or not np.isfinite(feature).all():
                        raise ValueError("invalid feature output")
                    row_features.append((flip, brightness, feature))
                identity_features[row["index"]] = next(f for flip, brightness, f in row_features
                                                       if not flip and brightness == 1.0)
                if row["split"] == "train":
                    train_features.extend(f for _, _, f in row_features)
                    train_labels.extend([row["label"]] * len(row_features))
                    train_groups.extend([row["source_sha256"]] * len(row_features))
                record.update(status="features_ready", augmentations=len(variants))
            except (ValueError, OSError) as exc:
                record.update(status="unknown", state="unknown", reason=str(exc)[:250])
            record["feature_sec"] = time.monotonic()-row_started
            checkpoint()
            print(json.dumps({"row": row["index"], "split": row["split"], "status": record["status"],
                              "feature_sec": record["feature_sec"]}), flush=True)
        assert set(train_groups) <= train_hashes and not set(train_groups) & probe_hashes
        report["training_augmented_samples"] = len(train_features)
        head = fit(train_features, train_labels, train_groups)
        assert head["dimension"] == 3840 and set(head["train_group_hashes"]) <= train_hashes
        head.update(backbone_pin=download, preprocess=report["preprocess"], labels_sha256=report["labels_sha256"],
                    source_sha256=report["source_sha256"], preregister_sha256=report["preregister_sha256"],
                    head_code_sha256=report["head_code_sha256"], score_semantics="region presence; not detection boxes or ownership")
        write(args.out / "head.json", head)
        loaded = json.loads((args.out / "head.json").read_text())
        for record in report["rows"]:
            if record["index"] in identity_features and record["status"] == "features_ready":
                record.update(predict(identity_features[record["index"]], loaded))
        report["confusion"] = {split: confusion([r for r in report["rows"] if r["split"] == split])
                               for split in ("train", "probe")}
        report.update(status="trained", head_sha256=digest(args.out / "head.json"),
                      probe_used_for_fit=False, probe_augmentations=0)
        checkpoint()
        print(json.dumps({"status": "trained", "elapsed_sec": report["elapsed_sec"],
                          "confusion": report["confusion"]}), flush=True)
    except Exception as exc:
        report.update(status="error", error={"type": type(exc).__name__, "message": str(exc)[:1000]})
        checkpoint()
        raise


if __name__ == "__main__":
    main()
