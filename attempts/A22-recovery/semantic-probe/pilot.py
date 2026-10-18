"""Offline target semantics pilot; local in-memory pixels, numeric/text output only."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

CLASSES = {
    "banknotes",
    "id_card",
    "phone",
    "paper_document",
    "cloth_personal_item",
    "other",
    "unknown",
}
PROMPT = (
    "Image 1 is the full frame. Image 2 is a 128-pixel native context crop of the same location. "
    "A red rectangle in both images marks exactly one target object. Classify only the visible "
    "object inside that rectangle, ignoring other objects elsewhere. Choose one class: banknotes, "
    "id_card, phone, paper_document, cloth_personal_item, other, unknown. Use banknotes only for "
    "clearly recognizable banknotes or banknote bundles; "
    "use id_card only for a clearly recognizable "
    "identity card. A plain rectangle is insufficient. Use unknown if the target is unclear or "
    'occluded. Return only JSON with exactly one key: {"class":"unknown"}.'
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_answer(raw):
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate keys")
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if (
        not isinstance(value, dict)
        or set(value) != {"class"}
        or type(value["class"]) is not str
        or value["class"] not in CLASSES
    ):
        raise ValueError("invalid class response")
    return value["class"]


def iou(a, b):
    common = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return common / max(
        1e-12, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - common
    )


def select(native, dino):
    secondary = {(r["sha256"], r["t"]): r for r in dino}
    queues, no_proposal = [], []
    for row in native:
        key = (row["sha256"], row["t"])
        other = secondary[key]
        width, height = other["source_size_wh"]
        groups = []
        for source, calls in [
            ("owlv2_native128", row["variants"]["full_desk_plus_native128"]["calls"]),
            ("grounding_dino_base", other["calls"]),
        ]:
            candidates = []
            for call_index, call in enumerate(calls):
                if not call.get("ok") or call.get("invalid_output_values", 0):
                    continue
                for detection in call["detections"]:
                    box, score = detection["box"], detection["score"]
                    if detection["label"] not in {"cash", "bundle", "id_card"}:
                        continue
                    if not all(math.isfinite(v) and 0 <= v <= 1 for v in [*box, score]):
                        continue
                    x1, y1, x2, y2 = box
                    if not (0 < (x2 - x1) * width <= 128 and 0 < (y2 - y1) * height <= 128):
                        continue
                    candidates.append(
                        {
                            "detection": detection,
                            "source": source,
                            "call_index": call_index,
                            "source_crop": call.get("crop", call.get("crop_xyxy_px")),
                            "source_proposal": call.get("proposal", call.get("name")),
                            "proposal_seed_t": call.get("source_t"),
                            "nn_inference_t": row["t"],
                            "source_model": call.get(
                                "source",
                                "IDEA-Research/grounding-dino-base@12bdfa3120f3e7ec7b434d90674b3396eccf88eb",
                            ),
                        }
                    )
            candidates.sort(
                key=lambda p: (-p["detection"]["score"], p["call_index"], p["detection"]["box"])
            )
            groups.append(candidates)
        queue = []
        for rank in range(max(map(len, groups), default=0)):
            for group in groups:
                if rank < len(group) and not any(
                    iou(group[rank]["detection"]["box"], p["detection"]["box"]) >= 0.5
                    for p in queue
                ):
                    queue.append(
                        {
                            **group[rank],
                            "clip": row["clip"],
                            "t": row["t"],
                            "sha256": row["sha256"],
                            "size": [width, height],
                        }
                    )
        if not queue:
            no_proposal.append({"clip": row["clip"], "t": row["t"], "status": "no_proposal"})
        queues.append(queue)
    selected = []
    for rank in range(max(map(len, queues), default=0)):
        for queue in queues:
            if rank < len(queue) and len(selected) < 24:
                selected.append(queue[rank])
    return selected, no_proposal


def self_check():
    assert parse_answer('{"class":"unknown"}') == "unknown"
    for raw in [
        '{"class":"cash"}',
        '{"class":"phone","confidence":90}',
        '{"class":"phone","class":"id_card"}',
        '```json\n{"class":"banknotes"}\n```',
    ]:
        try:
            parse_answer(raw)
        except (ValueError, TypeError):
            continue
        raise AssertionError("invalid response accepted")
    print("strict parser checks passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["native", "dino", "model", "videos", "out", "registration"]:
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    policy = json.loads(args.registration.read_text())
    for key in ["native", "dino"]:
        if digest(getattr(args, key).read_bytes()) != policy["input_hashes"][key]:
            raise ValueError("proposal source changed")
    model_meta = json.loads((args.model / "download-manifest.json").read_text())
    if model_meta["repo_id"] != policy["model"] or model_meta["revision"] != policy["revision"]:
        raise ValueError("model checkpoint mismatch")
    native, dino = json.loads(args.native.read_text()), json.loads(args.dino.read_text())
    selected, no_proposal = select(native, dino)
    if selected != policy["queries"] or PROMPT != policy["prompt"]:
        raise ValueError("frozen query/prompt mismatch")
    args.out.mkdir(parents=True, exist_ok=False)
    metadata = {
        "model": policy["model"],
        "revision": policy["revision"],
        "registration_sha256": digest(args.registration.read_bytes()),
        "model_manifest_sha256": digest((args.model / "download-manifest.json").read_bytes()),
        "script_sha256": digest(Path(__file__).read_bytes()),
        "no_proposal": no_proposal,
        "queries": len(selected),
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    lock_path = Path.home() / ".cache/datathon-workers/gpu.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        import cv2
        import torch
        from PIL import Image, ImageDraw
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        if not torch.cuda.is_available():
            raise RuntimeError("orchestrator CUDA execution required")
        started = time.monotonic()
        deadline = started + 240
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(args.model),
            dtype=torch.bfloat16,
            device_map="cuda",
            attn_implementation="sdpa",
            local_files_only=True,
        ).eval()
        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
        metadata["load_sec"] = time.monotonic() - started
        videos = {
            int(m.group(1)): p
            for p in args.videos.glob("*.mov")
            if (m := re.search(r"(\d+)$", p.stem))
        }
        checked, results = set(), []
        for query in selected:
            begin = time.monotonic()
            result = {
                **query,
                "answer": "unknown",
                "status": "not_run",
                "decision": "unknown",
                "returned_detection": None,
            }
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError("pilot deadline")
                video = videos[int(query["clip"].split("-")[-1])]
                if query["sha256"] not in checked:
                    with video.open("rb") as stream:
                        actual_sha = hashlib.file_digest(stream, "sha256").hexdigest()
                    if actual_sha != query["sha256"]:
                        raise ValueError("video hash mismatch")
                    checked.add(actual_sha)
                cap = cv2.VideoCapture(str(video))
                try:
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    cap.set(cv2.CAP_PROP_POS_MSEC, query["t"] * 1000)
                    ok, pixels = cap.read()
                    decoded_t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    if not ok or fps <= 0 or abs(decoded_t - query["t"]) > 1 / fps + 0.001:
                        raise ValueError("frame decode/time mismatch")
                    image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
                finally:
                    cap.release()
                w, h = image.size
                if [w, h] != query["size"]:
                    raise ValueError("source dimensions mismatch")
                a, b, c, d = query["detection"]["box"]
                box = [a * w, b * h, c * w, d * h]
                left = min(max(round((a + c) * w / 2 - 64), 0), w - 128)
                top = min(max(round((b + d) * h / 2 - 64), 0), h - 128)
                bounds = [left, top, left + 128, top + 128]
                crop = image.crop(bounds)
                marked = image.copy()
                ImageDraw.Draw(marked).rectangle(box, outline=(255, 0, 0), width=2)
                marked_crop = crop.copy()
                ImageDraw.Draw(marked_crop).rectangle(
                    [box[0] - left, box[1] - top, box[2] - left, box[3] - top],
                    outline=(255, 0, 0),
                    width=2,
                )
                result.update(
                    decoded_t=decoded_t,
                    context_crop=bounds,
                    source_rgb_sha256=digest(image.tobytes()),
                    context_rgb_sha256=digest(crop.tobytes()),
                    overlay_rgb_sha256=digest(marked.tobytes()),
                    context_overlay_rgb_sha256=digest(marked_crop.tobytes()),
                )
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "image"},
                            {"type": "text", "text": PROMPT},
                        ],
                    }
                ]
                text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                inputs = processor(
                    text=[text],
                    images=[marked, marked_crop],
                    size={"shortest_edge": 65536, "longest_edge": 1048576},
                    return_tensors="pt",
                ).to(model.device)
                inputs.pop("token_type_ids", None)
                remaining = min(15.0, deadline - time.monotonic())
                if remaining <= 0:
                    raise TimeoutError("query deadline")
                torch.cuda.synchronize()
                infer = time.monotonic()
                with torch.inference_mode():
                    output = model.generate(
                        **inputs, max_new_tokens=32, do_sample=False, max_time=remaining
                    )
                torch.cuda.synchronize()
                if time.monotonic() > deadline:
                    raise TimeoutError("pilot deadline after generation")
                generated = output[:, inputs["input_ids"].shape[1] :]
                raw = processor.batch_decode(
                    generated, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )[0].strip()
                answer = parse_answer(raw)
                result.update(
                    raw=raw,
                    answer=answer,
                    status="ok",
                    decision=(
                        "accepted"
                        if answer in {"banknotes", "id_card"}
                        else "unknown"
                        if answer == "unknown"
                        else "rejected"
                    ),
                    inference_sec=time.monotonic() - infer,
                    image_grid_thw=inputs["image_grid_thw"].detach().cpu().tolist(),
                )
                if answer in {"banknotes", "id_card"}:
                    result["returned_detection"] = {
                        **query["detection"],
                        "track_id": "",
                        "role": "unknown",
                    }
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                result.update(status="error", error_type=type(exc).__name__, error=str(exc))
            result["wall_sec"] = time.monotonic() - begin
            results.append(result)
            (args.out / "results.json").write_text(
                json.dumps(results, indent=2, allow_nan=False) + "\n"
            )
            print(
                json.dumps(
                    {"done": len(results), "answer": result["answer"], "status": result["status"]}
                ),
                flush=True,
            )
        metadata.update(
            total_sec=time.monotonic() - started,
            peak_gpu_bytes=torch.cuda.max_memory_allocated(),
            completed=len(results),
            errors=sum(r["status"] != "ok" for r in results),
        )
        (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return 2 if metadata["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
