#!/usr/bin/env python3
"""A27: zero-shot cash detection with commercially licensed open-vocabulary detectors.

Scores the 12 frame-presence labels from A24's manifest with each model, as frozen in
PREREGISTER.md. Writes numbers to <out>/results.json and <out>/summary.json, and overlay
images to <out>/img/ (for human review on the VM only).

    python run.py --manifest label-manifest.json --videos ~/data/open/videos --out ~/a27_out \
        --models owl-base,owl-large,mmgdino-large,sam3
"""

import argparse
import gc
import hashlib
import json
import time
from pathlib import Path

import cv2
import torch
from PIL import Image, ImageDraw

PROMPTS = ["banknotes", "stack of paper money", "bundle of cash"]
CHECKPOINTS = {
    "owl-base": "google/owlv2-base-patch16-ensemble",
    "owl-large": "google/owlv2-large-patch14-ensemble",
    "mmgdino-large": "openmmlab-community/mm_grounding_dino_large_all",
    "sam3": "facebook/sam3",
}
DEFAULT_THRESHOLDS = {"owl-base": 0.15, "owl-large": 0.15, "mmgdino-large": 0.30, "sam3": 0.5}
TILE_FRACTION, TILE_OFFSETS = 0.6, (0.0, 0.4)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frames(manifest: Path, videos: Path) -> list[dict]:
    records = json.loads(manifest.read_text())["records"]
    by_hash = {sha256(p): p for p in sorted(videos.iterdir()) if p.is_file()}
    frames = []
    for r in records:
        path = by_hash.get(r["video_sha256"])
        if path is None:
            raise FileNotFoundError(f"no video with sha256 {r['video_sha256']} for {r['clip']}")
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_MSEC, r["t"] * 1000)
        ok, bgr = cap.read()
        actual_t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        cap.release()
        if not ok:
            raise RuntimeError(f"cannot read {path} at {r['t']} s")
        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        frames.append({"clip": r["clip"], "t": r["t"], "decoded_t": actual_t,
                       "cash_visible": r["cash_visible"], "image": image})
    return frames


def views(image: Image.Image) -> list[tuple[str, tuple[int, int, int, int]]]:
    w, h = image.size
    tw, th = round(w * TILE_FRACTION), round(h * TILE_FRACTION)
    out = [("full", (0, 0, w, h))]
    for oy in TILE_OFFSETS:
        for ox in TILE_OFFSETS:
            x0, y0 = round(w * ox), round(h * oy)
            out.append((f"tile_{ox:.1f}_{oy:.1f}", (x0, y0, min(w, x0 + tw), min(h, y0 + th))))
    return out


class Owl:
    def __init__(self, checkpoint: str, device: str):
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        self.proc = Owlv2Processor.from_pretrained(checkpoint)
        self.model = Owlv2ForObjectDetection.from_pretrained(checkpoint).to(device).eval()
        self.device = device

    @torch.no_grad()
    def best(self, image: Image.Image, prompt: str) -> tuple[float, list[float]]:
        inputs = self.proc(text=[[prompt]], images=image, return_tensors="pt").to(self.device)
        out = self.model(**inputs)
        side = max(image.size)  # OWLv2 pads to a square at bottom/right
        res = self.proc.post_process_grounded_object_detection(
            out, threshold=0.0, target_sizes=[(side, side)])[0]
        i = int(res["scores"].argmax())
        return float(res["scores"][i]), [float(v) for v in res["boxes"][i]]


class MMGroundingDino:
    def __init__(self, checkpoint: str, device: str):
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        self.proc = AutoProcessor.from_pretrained(checkpoint)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(checkpoint).to(device).eval()
        self.device = device

    @torch.no_grad()
    def best(self, image: Image.Image, prompt: str) -> tuple[float, list[float]]:
        inputs = self.proc(images=image, text=f"{prompt}.", return_tensors="pt").to(self.device)
        out = self.model(**inputs)
        res = self.proc.post_process_grounded_object_detection(
            out, inputs.input_ids, threshold=0.0, text_threshold=0.0,
            target_sizes=[image.size[::-1]])[0]
        i = int(res["scores"].argmax())
        return float(res["scores"][i]), [float(v) for v in res["boxes"][i]]


class Sam3:
    def __init__(self, checkpoint: str, device: str):
        from transformers import Sam3Model, Sam3Processor

        self.proc = Sam3Processor.from_pretrained(checkpoint)
        self.model = Sam3Model.from_pretrained(checkpoint).to(device).eval()
        self.device = device

    @torch.no_grad()
    def best(self, image: Image.Image, prompt: str) -> tuple[float, list[float]]:
        inputs = self.proc(images=image, text=prompt, return_tensors="pt").to(self.device)
        out = self.model(**inputs)
        res = self.proc.post_process_instance_segmentation(
            out, threshold=0.0, mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist())[0]
        if len(res["scores"]) == 0:
            return 0.0, [0.0, 0.0, 0.0, 0.0]
        i = int(res["scores"].argmax())
        return float(res["scores"][i]), [float(v) for v in res["boxes"][i]]


MODEL_CLASSES = {"owl-base": Owl, "owl-large": Owl, "mmgdino-large": MMGroundingDino, "sam3": Sam3}


def score_frame(model, image: Image.Image) -> list[dict]:
    rows = []
    for view, (x0, y0, x1, y1) in views(image):
        crop = image.crop((x0, y0, x1, y1))
        for prompt in PROMPTS:
            score, box = model.best(crop, prompt)
            rows.append({"view": view, "prompt": prompt, "score": score,
                         "box": [box[0] + x0, box[1] + y0, box[2] + x0, box[3] + y0]})
    return rows


def auroc(pos: list[float], neg: list[float]) -> float:
    pairs = [(p > n) + 0.5 * (p == n) for p in pos for n in neg]
    return sum(pairs) / len(pairs)


def summarize(results: list[dict]) -> dict:
    summary = {}
    for name in dict.fromkeys(r["model"] for r in results):
        thr = DEFAULT_THRESHOLDS[name]
        rows = [r for r in results if r["model"] == name]
        per_variant = {}
        for variant, keep in (("full", lambda v: v == "full"), ("full+tiles", lambda v: True)):
            scores = [(max(d["score"] for d in r["detections"] if keep(d["view"])), r["cash_visible"])
                      for r in rows]
            pos = [s for s, y in scores if y]
            neg = [s for s, y in scores if not y]
            per_variant[variant] = {
                "auroc": round(auroc(pos, neg), 4),
                "margin": round(min(pos) - max(neg), 4),
                "threshold": thr,
                "tp": sum(s >= thr for s in pos), "fn": sum(s < thr for s in pos),
                "tn": sum(s < thr for s in neg), "fp": sum(s >= thr for s in neg),
            }
        summary[name] = {
            "checkpoint": CHECKPOINTS[name],
            "variants": per_variant,
            "mean_seconds_per_frame_all_views": round(sum(r["seconds"] for r in rows) / len(rows), 3),
        }
    return summary


def draw(image: Image.Image, det: dict, title: str) -> Image.Image:
    im = image.copy()
    d = ImageDraw.Draw(im)
    d.rectangle(det["box"], outline="#00c853", width=3)
    d.rectangle([0, 0, im.width, 18], fill="black")
    d.text((4, 3), f"{title} | {det['prompt']} {det['score']:.3f} ({det['view']})", fill="white")
    return im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", default="owl-base,owl-large,mmgdino-large,sam3")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    (args.out / "img").mkdir(parents=True, exist_ok=True)
    frames = load_frames(args.manifest, args.videos)
    results, failures = [], {}
    for name in args.models.split(","):
        try:
            model = MODEL_CLASSES[name](CHECKPOINTS[name], device)
        except OSError as exc:  # gated or missing checkpoint: record it, keep the other models
            failures[name] = f"{type(exc).__name__}: {exc}".splitlines()[0]
            print(f"[{name}] not loaded: {failures[name]}", flush=True)
            continue
        for f in frames:
            start = time.perf_counter()
            dets = score_frame(model, f["image"])
            seconds = time.perf_counter() - start
            top = max(dets, key=lambda d: d["score"])
            draw(f["image"], top, name).save(args.out / "img" / f"{f['clip']}_{f['t']}_{name}.jpg")
            results.append({"model": name, "clip": f["clip"], "t": f["t"], "decoded_t": f["decoded_t"],
                            "cash_visible": f["cash_visible"], "seconds": round(seconds, 3),
                            "detections": dets})
            print(f"[{name}] {f['clip']}@{f['t']} cash={f['cash_visible']} "
                  f"max={top['score']:.3f} ({top['view']}, {top['prompt']}) {seconds:.2f}s", flush=True)
        del model
        gc.collect()
        torch.cuda.empty_cache()

    meta = {"device": device, "torch": torch.__version__,
            "transformers": __import__("transformers").__version__, "failures": failures}
    (args.out / "results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=1))
    summary = {"meta": meta, "models": summarize(results)}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
