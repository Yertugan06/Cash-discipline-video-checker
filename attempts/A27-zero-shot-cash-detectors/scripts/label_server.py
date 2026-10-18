#!/usr/bin/env python3
"""A27 box review page: mark each detector's top box as cash / not cash / unclear, draw missed cash.

Runs on the VM next to the frames (they must not leave it for cloud tools). Standard library
plus the OpenCV/Pillow already used by run.py. Labels go to <out>/box-labels.json on every change.

    python label_server.py --manifest label-manifest.json --videos ~/data/open/videos --out ~/a27_out
    # locally: ssh -N -L 8200:127.0.0.1:8200 datathon  ->  http://localhost:8200
"""

import argparse
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from run import load_frames

VERDICTS = {"cash", "not_cash", "unclear"}
MERGE_IOU = 0.5


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def candidates(results: list[dict], key: str) -> list[dict]:
    """Top box per model for one frame; boxes that overlap (IoU >= 0.5) are reviewed once."""
    merged: list[dict] = []
    for r in results:
        if f"{r['clip']}@{r['t']}" != key:
            continue
        top = max(r["detections"], key=lambda d: d["score"])
        box = [round(v, 1) for v in top["box"]]
        proposal = {"model": r["model"], "score": round(top["score"], 3),
                    "prompt": top["prompt"], "view": top["view"]}
        for c in merged:
            if iou(c["box"], box) >= MERGE_IOU:
                c["proposals"].append(proposal)
                break
        else:
            merged.append({"box": box, "proposals": [proposal]})
    for i, c in enumerate(merged):
        c["id"] = f"c{i}"
    return merged


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def save(self, key: str, entry: dict) -> None:
        self.data[key] = entry
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)


def validate(entry: object, item: dict) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("label must be an object")
    marks = entry.get("marks", {})
    ids = {c["id"]: c for c in item["candidates"]}
    if not isinstance(marks, dict) or any(k not in ids or v not in VERDICTS for k, v in marks.items()):
        raise ValueError("marks must map candidate ids to cash / not_cash / unclear")
    boxes = entry.get("drawn", [])
    w, h = item["width"], item["height"]
    if not isinstance(boxes, list) or not all(
            isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)
            and 0 <= b[0] < b[2] <= w and 0 <= b[1] < b[3] <= h for b in boxes):
        raise ValueError("drawn boxes must be [x0, y0, x1, y1] inside the frame")
    return {"marks": {k: {"verdict": v, "box": ids[k]["box"]} for k, v in marks.items()},
            "drawn": [[round(v, 1) for v in b] for b in boxes],
            "updated": datetime.now(UTC).isoformat(timespec="seconds")}


def make_handler(items: list[dict], jpegs: list[bytes], store: Store, page: bytes):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, code: int, obj: object) -> None:
            self.send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self) -> None:
            if self.path == "/":
                self.send(200, page, "text/html; charset=utf-8")
            elif self.path == "/api/items":
                self.send_json(200, {"items": items, "labels": store.data})
            elif self.path.startswith("/frame/") and self.path.endswith(".jpg"):
                idx = self.path[len("/frame/"):-len(".jpg")]
                if idx.isdigit() and int(idx) < len(jpegs):
                    self.send(200, jpegs[int(idx)], "image/jpeg")
                else:
                    self.send_json(404, {"error": "no such frame"})
            else:
                self.send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self.path.startswith("/api/label/"):
                return self.send_json(404, {"error": "not found"})
            key = unquote(self.path[len("/api/label/"):])
            item = next((i for i in items if i["key"] == key), None)
            if item is None:
                return self.send_json(404, {"error": f"unknown frame {key}"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                entry = validate(json.loads(self.rfile.read(length)), item)
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send_json(400, {"error": str(exc)})
            store.save(key, entry)
            self.send_json(200, entry)

        def log_message(self, fmt: str, *args) -> None:
            if not self.path.startswith("/frame/"):
                super().log_message(fmt, *args)

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="run.py output dir with results.json")
    ap.add_argument("--port", type=int, default=8200)
    args = ap.parse_args()

    results = json.loads((args.out / "results.json").read_text())["results"]
    frames = load_frames(args.manifest, args.videos)
    items, jpegs = [], []
    for i, f in enumerate(frames):
        key = f"{f['clip']}@{f['t']}"
        buf = io.BytesIO()
        f["image"].save(buf, format="JPEG", quality=92)
        jpegs.append(buf.getvalue())
        items.append({"key": key, "index": i, "clip": f["clip"], "t": f["t"],
                      "cash_visible": f["cash_visible"], "width": f["image"].width,
                      "height": f["image"].height, "candidates": candidates(results, key)})
    page = (Path(__file__).with_name("label_page.html")).read_bytes()
    store = Store(args.out / "box-labels.json")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(items, jpegs, store, page))
    print(f"serving {len(items)} frames on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
