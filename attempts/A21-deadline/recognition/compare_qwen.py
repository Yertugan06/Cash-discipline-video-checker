#!/usr/bin/env python3
"""Frozen local Qwen presence probe; numeric/text artifacts only, no production hook."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import compare_objects as common

from backend.f1.object_refinement import SourceCrop

CLASSES = ("cash", "id_card")


def parse_answer(raw: str) -> dict:
    def unique_keys(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate answer keys")
        return result

    answer = json.loads(raw, object_pairs_hook=unique_keys)
    if not isinstance(answer, dict) or set(answer) != set(CLASSES):
        raise ValueError("Answer must contain exactly cash and id_card")
    if any(type(v) is not str or v not in {"yes", "no", "unknown"} for v in answer.values()):
        raise ValueError("Answers must be explicit yes, no or unknown")
    return {k: {"yes": True, "no": False, "unknown": None}[v] for k, v in answer.items()}


def union_answers(calls: list[dict]) -> dict:
    result = {
        "pred": {},
        "sec": sum(c.get("sec", 0) for c in calls),
        "failed_crops": sum(c["status"] not in {"ok", "pending"} for c in calls),
        "invalid_output_values": 0,
    }
    for key in CLASSES:
        values = [c.get("pred", {}).get(key) if c["status"] == "ok" else None for c in calls]
        result["pred"][key] = (
            True
            if any(v is True for v in values)
            else False
            if values and all(v is False for v in values)
            else None
        )
    return result


def request_content(manifest: dict, temporal: bool) -> list[dict]:
    # Filenames, timestamps, labels and organizer outcomes never reach the model prompt.
    instruction = manifest["temporal_instruction" if temporal else "single_instruction"]
    return [{"type": "image"} for _ in range(3 if temporal else 1)] + [
        {"type": "text", "text": instruction + "\n" + manifest["prompt"]}
    ]


def prepare_inputs(processor, images: list, manifest: dict):
    messages = [{"role": "user", "content": request_content(manifest, len(images) == 3)}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(
        text=[text], images=images, size=manifest["processor_size"], return_tensors="pt"
    )
    inputs.pop("token_type_ids", None)
    return inputs


def generate(model, processor, images: list, manifest: dict, remaining_sec: float) -> dict:
    # Same local load/template/generate/decode path as realtime/descriptions.py.
    import torch

    if remaining_sec <= 0:
        return {"status": "budget_expired"}
    started = time.monotonic()
    inputs = prepare_inputs(processor, images, manifest).to(model.device)
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=manifest["max_new_tokens"],
            do_sample=False,
            max_time=min(manifest["max_call_sec"], remaining_sec),
        )
    torch.cuda.synchronize()
    generated = output[:, inputs["input_ids"].shape[1] :]
    raw = processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
    result = {
        "raw": raw,
        "sec": time.monotonic() - started,
        "input_tokens": int(inputs["input_ids"].shape[1]),
        "output_tokens": int(generated.shape[1]),
        "image_grid_thw": inputs["image_grid_thw"].detach().cpu().tolist(),
    }
    try:
        result.update(status="ok", pred=parse_answer(raw))
    except (ValueError, TypeError) as exc:
        result.update(status="invalid_response", error=str(exc))
    return result


def initial_records(manifest: dict) -> list[dict]:
    records = []
    for case in manifest["cases"]:
        calls = {}
        width, height = case["source_size_wh"]
        for variant, spec in manifest["variants"].items():
            boxes = [[0, 0, width, height]] if spec["crop"] == "full" else case["tiles_xyxy_px"]
            calls[variant] = [
                {"box_px": box, "offsets_sec": spec["offsets_sec"], "status": "pending"}
                for box in boxes
            ]
        records.append({**case, "calls": calls})
    return records


def save(out: Path, manifest: dict, records: list[dict], metadata: dict) -> None:
    for record in records:
        record["variants"] = {v: union_answers(calls) for v, calls in record["calls"].items()}
    summary = common.summarise(records, variants=manifest["variants"], classes=CLASSES)
    for variant, stats in summary.items():
        statuses = [c["status"] for r in records for c in r["calls"][variant]]
        stats["invalid_responses"] = statuses.count("invalid_response")
        stats["not_run_calls"] = sum(s in {"pending", "budget_expired"} for s in statuses)
    common.write_json(out / "results.json", records)
    common.write_json(out / "summary.json", summary)
    common.write_json(out / "metadata.json", metadata)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    manifest = json.loads(args.manifest.read_text())
    records = initial_records(manifest)
    metadata = {
        "status": "preflight" if args.preflight else "loading",
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_repo": manifest["model_repo"],
        "model_revision": manifest["model_revision"],
        "config_sha256": hashlib.sha256((args.model / "config.json").read_bytes()).hexdigest(),
        "weight_files": [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(args.model.glob("*.safetensors"))
        ],
        "prompt": manifest["prompt"],
        "precision": "bfloat16",
        "device": "cuda",
        "limit_sec": manifest["inference_budget_sec"],
    }
    if not metadata["weight_files"]:
        raise ValueError("No local model weights found")
    save(args.out, manifest, records, metadata)
    if args.preflight:
        from transformers import AutoProcessor

        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
        checks = []
        for record in records:
            path = common.find_video(args.videos, record["clip"])
            frames = {}
            for offset in (-0.4, 0.0, 0.4):
                image, frame_meta = common.grab_frame(path, record["t"] + offset)
                if list(image.size) != record["source_size_wh"]:
                    raise ValueError("Source dimensions differ from frozen manifest")
                frames[offset] = image
                checks.append({"clip": record["clip"], "offset": offset, **frame_meta})
            # CPU processor smoke check on the first case, both single and triple images.
            if len(checks) == 3:
                box = record["tiles_xyxy_px"][0]
                for images in ([frames[0.0]], [frames[o].crop(box) for o in (-0.4, 0.0, 0.4)]):
                    inputs = prepare_inputs(processor, images, manifest)
                    checks.append(
                        {
                            "processor_images": len(images),
                            "image_grid_thw": inputs["image_grid_thw"].tolist(),
                            "input_tokens": int(inputs["input_ids"].shape[1]),
                        }
                    )
        common.write_json(args.out / "preflight.json", checks)
        metadata["status"] = "preflight_ok"
        save(args.out, manifest, records, metadata)
        print(json.dumps({"status": "preflight_ok", "cases": len(records)}), flush=True)
        return 0

    started = time.monotonic()
    try:
        import torch
        import transformers
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        torch.set_num_threads(2)
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(args.model),
            dtype=torch.bfloat16,
            device_map="cuda",
            attn_implementation="sdpa",
            local_files_only=True,
        ).eval()
        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
    except Exception as exc:
        metadata.update(status="model_unavailable", error=f"{type(exc).__name__}: {exc}")
        save(args.out, manifest, records, metadata)
        print(json.dumps({"status": "model_unavailable", "error": metadata["error"]}), flush=True)
        return 2
    metadata.update(
        status="running",
        load_sec=time.monotonic() - started,
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
    )
    deadline = time.monotonic() + manifest["inference_budget_sec"]
    save(args.out, manifest, records, metadata)
    # Round-robin inputs/variants so a cutoff does not silently drop all clean negatives.
    max_crops = max(len(calls) for r in records for calls in r["calls"].values())
    tasks = [
        (r, variant, index)
        for index in range(max_crops)
        for variant in manifest["variants"]
        for r in records
        if index < len(r["calls"][variant])
    ]
    for record, variant, index in tasks:
        call = record["calls"][variant][index]
        if time.monotonic() >= deadline:
            call["status"] = "budget_expired"
            continue
        try:
            path = common.find_video(args.videos, record["clip"])
            images, frame_metadata = [], []
            crop = SourceCrop(*call["box_px"])
            for offset in call["offsets_sec"]:
                image, frame_meta = common.grab_frame(path, record["t"] + offset)
                if list(image.size) != record["source_size_wh"]:
                    raise ValueError("Source dimensions differ from frozen manifest")
                crop.validate(*image.size)
                images.append(image.crop(crop.bounds))
                frame_metadata.append(frame_meta)
            call["frames"] = frame_metadata
            call.update(generate(model, processor, images, manifest, deadline - time.monotonic()))
        except Exception as exc:
            call.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        metadata["inference_sec"] = time.monotonic() - deadline + manifest["inference_budget_sec"]
        save(args.out, manifest, records, metadata)
        print(
            json.dumps(
                {
                    "case": record["clip"],
                    "variant": variant,
                    "crop": index,
                    "status": call["status"],
                    "sec": call.get("sec"),
                }
            ),
            flush=True,
        )
    statuses = [c["status"] for r in records for calls in r["calls"].values() for c in calls]
    metadata.update(
        status="complete" if set(statuses) == {"ok"} else "complete_with_unknowns",
        inference_sec=time.monotonic() - deadline + manifest["inference_budget_sec"],
        planned_calls=len(tasks),
        completed_calls=statuses.count("ok"),
    )
    save(args.out, manifest, records, metadata)
    print(json.dumps(metadata), flush=True)
    return 0 if metadata["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
