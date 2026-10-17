"""Stage 1: stream-decode a video at ~5 fps, detect + track people (RT-DETR r18 + ByteTrack),
locate static scene objects once (OWLv2 on the first ~2 s), save sampled frames for later crops.

Weights are read from the teammate checker (read-only). Nothing here makes rule decisions.
"""
import json
import os
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

WEIGHTS = Path(os.environ.get("AGENTB_WEIGHTS", "/home/ubuntu/forte-cash-checker/weights"))
SAMPLE_FPS = 5.0
PERSON_SIZE = 512
PERSON_SCORE = 0.30
OWL_SIZE = 768
SCENE_PROMPTS = {
    "desk": ["a cash desk table", "an office desk", "a desk"],
    "safe": ["a grey metal safe cabinet", "a metal safe", "a metal cabinet"],
    "door": ["a glass door", "a door"],
    "laptop": ["a laptop computer", "a laptop"],
    "counter": ["a banknote counting machine", "a money counting machine"],
}
CALIB_TIMES = (0.0, 1.0, 2.0)

_MODELS = {}


def _models():
    if _MODELS:
        return _MODELS
    import torch
    from transformers import (Owlv2ForObjectDetection, Owlv2Processor, RTDetrForObjectDetection,
                              RTDetrImageProcessor)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    _MODELS["torch"] = torch
    _MODELS["dev"] = dev
    _MODELS["pp"] = RTDetrImageProcessor.from_pretrained(WEIGHTS / "person", local_files_only=True)
    _MODELS["pm"] = RTDetrForObjectDetection.from_pretrained(
        WEIGHTS / "person", local_files_only=True, use_safetensors=True).eval().to(dev)
    _MODELS["op"] = Owlv2Processor.from_pretrained(WEIGHTS / "objects", local_files_only=True)
    _MODELS["om"] = Owlv2ForObjectDetection.from_pretrained(
        WEIGHTS / "objects", local_files_only=True, use_safetensors=True,
        torch_dtype=torch.float16 if dev == "cuda" else torch.float32).eval().to(dev)
    return _MODELS


def _norm(box, w, h):
    x1, y1, x2, y2 = np.clip(np.asarray(box, float) / [w, h, w, h], 0, 1).tolist()
    return [x1, y1, x2, y2] if x2 - x1 > 0.005 and y2 - y1 > 0.005 else None


def detect_people(image):
    m = _models()
    torch = m["torch"]
    inp = m["pp"](images=image, size={"height": PERSON_SIZE, "width": PERSON_SIZE},
                  return_tensors="pt").to(m["dev"])
    with torch.inference_mode():
        out = m["pm"](**inp)
    res = m["pp"].post_process_object_detection(out, target_sizes=[(image.height, image.width)],
                                                threshold=PERSON_SCORE)[0]
    dets = []
    for b, s, l in zip(res["boxes"], res["scores"], res["labels"]):
        if int(l) != 0:
            continue
        nb = _norm(b.cpu().numpy(), image.width, image.height)
        if nb:
            dets.append((nb, float(s)))
    return _nms(dets, 0.5)


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def _nms(dets, thr):
    keep = []
    for d in sorted(dets, key=lambda x: -x[1]):
        if all(_iou(d[0], k[0]) < thr for k in keep):
            keep.append(d)
    return keep


def detect_scene_objects(image):
    m = _models()
    torch = m["torch"]
    labels = [lab for lab, ps in SCENE_PROMPTS.items() for _ in ps]
    prompts = [p for ps in SCENE_PROMPTS.values() for p in ps]
    tok = m["op"].tokenizer(prompts, padding="max_length", truncation=True, return_tensors="pt").to(m["dev"])
    pix = m["op"].image_processor(images=image, size={"height": OWL_SIZE, "width": OWL_SIZE},
                                  return_tensors="pt").to(m["dev"])
    if m["dev"] == "cuda":
        pix["pixel_values"] = pix["pixel_values"].half()
    with torch.inference_mode():
        out = m["om"](**pix, **tok, interpolate_pos_encoding=True)
    # OWLv2 pads to a square; target size must be the padded square to keep boxes aligned.
    side = max(image.width, image.height)
    res = m["op"].post_process_grounded_object_detection(out, threshold=0.08, target_sizes=[(side, side)])[0]
    dets = []
    for b, s, l in zip(res["boxes"], res["scores"], res["labels"]):
        nb = _norm(b.float().cpu().numpy(), image.width, image.height)
        if nb:
            dets.append({"label": labels[int(l)], "box": nb, "score": float(s)})
    return dets


def calibrate(cands):
    """Per label: densest cluster of candidate boxes over the calibration frames, median box."""
    objs = {}
    for lab in SCENE_PROMPTS:
        ms = [d for d in cands if d["label"] == lab]
        if not ms:
            continue
        best = max(ms, key=lambda d: sum(x["score"] for x in ms if _iou(d["box"], x["box"]) > 0.3))
        cl = [d for d in ms if _iou(best["box"], d["box"]) > 0.3]
        objs[lab] = {"box": np.median([d["box"] for d in cl], axis=0).tolist(),
                     "score": float(np.mean([d["score"] for d in cl])), "n": len(cl)}
    return objs


def run_detection(video_path, frames_dir, deadline=None):
    """Returns dict with scene objects, per-sample tracked people and timing. Frames saved as JPEG."""
    import cv2
    import supervision as sv
    from PIL import Image

    t0 = time.time()
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"cannot open video {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(fps / SAMPLE_FPS))
    tracker = sv.ByteTrack(track_activation_threshold=0.35, lost_track_buffer=int(SAMPLE_FPS * 3),
                           minimum_matching_threshold=0.8, frame_rate=int(SAMPLE_FPS),
                           minimum_consecutive_frames=2)
    samples, cands = [], []
    idx = -1
    W = H = None
    while True:
        ok = cap.grab()
        if not ok:
            break
        idx += 1
        if idx % step:
            continue
        ok, bgr = cap.retrieve()
        if not ok:
            break
        if deadline and time.time() > deadline:
            raise TimeoutError("detection exceeded deadline")
        t = idx / fps
        H, W = bgr.shape[:2]
        si = len(samples)
        cv2.imwrite(str(frames_dir / f"{si:05d}.jpg"), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        if any(abs(t - ct) < 0.5 / SAMPLE_FPS for ct in CALIB_TIMES):
            cands.extend(detect_scene_objects(image))
        dets = detect_people(image)
        sd = sv.Detections(xyxy=np.array([d[0] for d in dets], np.float32).reshape(-1, 4),
                           confidence=np.array([d[1] for d in dets], np.float32),
                           class_id=np.zeros(len(dets), int))
        tr = tracker.update_with_detections(sd)
        people = [{"tid": int(tid), "box": [round(float(v), 4) for v in b], "score": round(float(s), 3)}
                  for b, s, tid in zip(tr.xyxy, tr.confidence, tr.tracker_id)]
        raw = [{"box": [round(v, 4) for v in d[0]], "score": round(d[1], 3)} for d in dets]
        samples.append({"i": si, "t": round(t, 3), "people": people, "raw": raw})
    cap.release()
    if not samples:
        raise ValueError("no frames decoded")
    return {"video": str(video_path), "fps": fps, "n_frames": n_total, "width": W, "height": H,
            "sample_fps": SAMPLE_FPS, "duration": samples[-1]["t"], "scene": calibrate(cands),
            "scene_candidates": cands, "samples": samples, "detect_s": round(time.time() - t0, 2)}


def cached_detection(video_path, cache_dir, deadline=None):
    cache_dir = Path(cache_dir)
    out = cache_dir / "det.json"
    if out.is_file():
        return json.loads(out.read_text())
    det = run_detection(video_path, cache_dir / "frames", deadline)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(det))
    return det


if __name__ == "__main__":
    import sys
    gt = json.load(open(sys.argv[1]))
    root = Path(sys.argv[2])
    ids = sys.argv[3:] or list(gt)
    for k in ids:
        t = time.time()
        d = cached_detection(gt[k]["path"], root / k)
        print(k, "samples", len(d["samples"]), "scene", sorted(d["scene"]), "det_s", d["detect_s"],
              "wall", round(time.time() - t, 1), flush=True)
