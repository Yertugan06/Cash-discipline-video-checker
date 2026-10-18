#!/usr/bin/env python3
"""Post-hoc diagnostic (not pre-registered): does running all A13 queries in one OWLv2 pass hide cash?

For each frame, take the human-confirmed cash box (box-labels.json) and report, for OWLv2-base on
the full frame: the best cash-prompt score among predicted boxes overlapping it, and the label
that box gets when all A13 queries compete (argmax over queries, as A13's post-processing did).

    python diag_query_competition.py --manifest label-manifest.json \
        --videos ~/data/open/videos --out ~/a27_out --perception perception.yaml
"""

import argparse
import json
from pathlib import Path

import torch
from label_server import iou
from run import CHECKPOINTS, PROMPTS, load_frames

A13_QUERIES = [
    "banknotes",
    "stack of paper money",
    "bundle of cash",
    "green fabric bag",
    "cash collection bag",
    "id card",
    "plastic card",
    "open safe door",
    "open metal cabinet door",
    "cup",
    "drink bottle",
    "snack food",
    "coat",
    "handbag",
    "person",
    "laptop",
    "money counting machine",
    "metal safe",
    "glass door",
]


@torch.no_grad()
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--videos", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--perception", type=Path, required=True, help="config/perception.yaml")
    args = ap.parse_args()

    from transformers import Owlv2ForObjectDetection, Owlv2Processor

    labels = json.loads((args.out / "box-labels.json").read_text())
    proc = Owlv2Processor.from_pretrained(CHECKPOINTS["owl-base"])
    model = Owlv2ForObjectDetection.from_pretrained(CHECKPOINTS["owl-base"]).to("cuda").eval()
    rows = []
    for f in load_frames(args.manifest, args.videos):
        key = f"{f['clip']}@{f['t']}"
        cash_boxes = [
            m["box"] for m in labels.get(key, {}).get("marks", {}).values() if m["verdict"] == "cash"
        ]
        if not cash_boxes:
            continue
        inputs = proc(text=[A13_QUERIES], images=f["image"], return_tensors="pt").to("cuda")
        out = model(**inputs)
        probs = out.logits[0].sigmoid()  # (boxes, queries)
        side = max(f["image"].size)
        # raw boxes in prediction order, so row i of probs is box i (OWLv2 pads to a square)
        cx, cy, w, h = (out.pred_boxes[0] * side).unbind(-1)
        boxes = torch.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], dim=-1)
        cash_q = [A13_QUERIES.index(p) for p in PROMPTS]
        overlap = [i for i, b in enumerate(boxes.tolist()) if max(iou(b, c) for c in cash_boxes) >= 0.3]
        if not overlap:
            rows.append({"frame": key, "note": "no predicted box overlaps the confirmed cash box"})
            continue
        best = max(overlap, key=lambda i: float(probs[i, cash_q].max()))
        winner = int(probs[best].argmax())
        rows.append(
            {
                "frame": key,
                "cash_score": round(float(probs[best, cash_q].max()), 3),
                "argmax_label": A13_QUERIES[winner],
                "argmax_score": round(float(probs[best, winner]), 3),
            }
        )
    runtime = runtime_check(proc, model, labels, args)
    (args.out / "diag-query-competition.json").write_text(
        json.dumps({"a13_queries": rows, "runtime_full_frame": runtime}, indent=2)
    )
    for r in rows + runtime:
        print(r)


def runtime_check(proc, model, labels: dict, args) -> list[dict]:
    """Mirror backend/f1/perception.py objects() on the full frame: config/perception.yaml
    object_prompts in one pass, owl_image_size, threshold object_score, one label per box."""
    import yaml

    config = yaml.safe_load(args.perception.read_text())
    groups = config["object_prompts"]
    names = [label for label, prompts in groups.items() for _ in prompts]
    prompts = [p for values in groups.values() for p in values]
    size = int(config["owl_image_size"])
    text = proc.tokenizer(prompts, padding="max_length", truncation=True, return_tensors="pt").to("cuda")
    rows = []
    for f in load_frames(args.manifest, args.videos):
        key = f"{f['clip']}@{f['t']}"
        cash_boxes = [
            m["box"] for m in labels.get(key, {}).get("marks", {}).values() if m["verdict"] == "cash"
        ]
        if not cash_boxes:
            continue
        image = f["image"]
        pixels = proc.image_processor(
            images=image, size={"height": size, "width": size}, return_tensors="pt"
        ).to("cuda")
        out = model(**pixels, **text, interpolate_pos_encoding=True)
        res = proc.post_process_grounded_object_detection(
            out, threshold=config["object_score"], target_sizes=[(image.height, image.width)]
        )[0]
        on_cash = sorted(
            {
                (names[int(lab)], round(float(s), 3))
                for b, s, lab in zip(res["boxes"].tolist(), res["scores"], res["labels"], strict=True)
                if max(iou(b, c) for c in cash_boxes) >= 0.3
            },
            key=lambda x: -x[1],
        )
        rows.append({"frame": key, "runtime_labels_on_cash_box": on_cash})
    return rows


if __name__ == "__main__":
    main()
