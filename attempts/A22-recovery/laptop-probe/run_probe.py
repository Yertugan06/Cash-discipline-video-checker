#!/usr/bin/env python3
"""Frozen, local-only laptop sequence pilot; stdout and artifacts contain no pixels."""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = {"working", "locked", "closed", "unknown"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def select_times(times, exit_t, policy):
    selected = set()
    for offset in policy["offsets_sec"]:
        target = exit_t + offset
        if times and times[0] <= target <= times[-1]:
            sample = min(times, key=lambda t: (abs(t - target), t))
            if abs(sample - target) <= policy["sample_tolerance_sec"]:
                selected.add(sample)
    return sorted(selected)


def parse_states(raw, count):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or set(value) != {"states"}:
        raise ValueError("invalid_schema")
    answers = value["states"]
    if not isinstance(answers, list) or len(answers) != count:
        raise ValueError("wrong_state_count")
    if any(not isinstance(s, str) or s not in STATES for s in answers):
        raise ValueError("invalid_state")
    return answers


def self_check():
    policy = {"offsets_sec": [-3, -2, -1, 0], "sample_tolerance_sec": 0.251}
    assert select_times([0, 0.5, 1, 2, 3], 3, policy) == [0, 1, 2, 3]
    assert select_times([0, 1, 3], 2, policy) == [0, 1]  # Never bridge a gap/cutoff.
    assert select_times([], 3, policy) == []
    assert parse_states('{"states":["working","unknown","closed"]}', 3) == [
        "working",
        "unknown",
        "closed",
    ]
    for raw in (
        '{"states":["unlocked"]}',
        '{"states":["closed"],"confidence":1}',
        '{"states":[],"states":["closed"]}',
        '{"states":[]}',
    ):
        try:
            parse_states(raw, 1)
        except (ValueError, TypeError):
            continue
        raise AssertionError("invalid output accepted")
    print("selection/strict-parser assertions passed")


def prepare(args, policy):
    sys.path.insert(0, str(args.base.resolve()))
    import cv2
    from PIL import Image

    from backend.f1.calibration import calibrate
    from backend.f1.events import build_events
    from backend.f1.perception import load_perception_config
    from backend.f1.vision_types import Observation, Scene

    cv2.setNumThreads(2)
    config = load_perception_config(args.base / "config/perception.yaml")
    index = [
        json.loads(s)
        for s in (args.base / "data/prepared/videos.jsonl").read_text().splitlines()
        if s.strip()
    ]
    records, jobs = [], []
    for number in policy["evaluation_inputs"]:
        started = time.monotonic()
        row = next(r for r in index if int(r["original_id"].split("-")[-1]) == number)
        sha = row["sha256"]
        video = next(
            p
            for p in args.videos.iterdir()
            if p.stem.replace("Х", "X") == f"X-{number}" and p.suffix.lower() == ".mov"
        )
        if file_hash(video) != sha:
            raise ValueError("video_hash_mismatch")
        cache = max((args.cache / sha).glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        payload = json.loads(cache.read_text())
        observations = [Observation.model_validate(o) for o in payload["observations"]]
        scene = Scene.model_validate(payload["scene"])
        if scene.candidates:
            scene = calibrate(scene.candidates, args.base / "config/overrides.yaml", sha)
        log = build_events(scene, observations, config, 2, observations[-1].timestamp_sec + 0.5)
        exits = [
            e
            for e in log.events
            if e.type == "EXIT"
            and e.facts.get("role") == "cashier"
            and e.facts.get("confirmed_exit", True) is True
        ]
        record = {
            "evaluation_input": number,
            "source_sha256": sha,
            "cache_sha256": file_hash(cache),
            "status": "triggered" if exits else "no_trigger",
            "sequences": [],
        }
        laptop = scene.objects.get("laptop")
        if exits and (
            laptop is None
            or not all(math.isfinite(x) and 0 <= x <= 1 for x in laptop.box)
            or laptop.box[2] <= laptop.box[0]
            or laptop.box[3] <= laptop.box[1]
        ):
            record["status"] = "missing_laptop_geometry"
            records.append(record)
            continue
        capture = cv2.VideoCapture(str(video))
        if not capture.isOpened():
            raise ValueError("video_unavailable")
        try:
            decoded = {}

            def frame(t, capture=capture, decoded=decoded):
                if t not in decoded:
                    capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                    ok, pixels = capture.read()
                    actual = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                    if not ok or abs(actual - t) > policy["decode_tolerance_sec"]:
                        raise ValueError("decode_time_mismatch")
                    decoded[t] = (pixels, actual)
                return decoded[t]

            times = sorted({o.timestamp_sec for o in observations})
            for event in exits:
                anchor = event.timestamp_sec
                selected = set(select_times(times, anchor, policy))
                candidates = [
                    t
                    for t in times
                    if max(0, anchor - policy["luminance_window_sec"]) <= t <= anchor
                ]
                means = [
                    (t, float(cv2.cvtColor(frame(t)[0], cv2.COLOR_BGR2GRAY).mean()))
                    for t in candidates
                ]
                drops = []
                for (before, bright), (after, dark) in zip(means, means[1:], strict=False):
                    if (
                        after - before <= 0.501
                        and bright - dark >= policy["luminance_drop_min"]
                        and dark <= bright * policy["luminance_ratio_max"]
                    ):
                        selected.add(before)
                        drops.append(
                            {
                                "before_t": before,
                                "after_t": after,
                                "before_mean": bright,
                                "after_mean": dark,
                            }
                        )
                sequence = {
                    "exit": event.model_dump(),
                    "luminance_samples": means,
                    "luminance_drops": drops,
                    "samples": [],
                }
                images = []
                for t in sorted(selected):
                    pixels, actual = frame(t)
                    h, w = pixels.shape[:2]
                    x1, y1, x2, y2 = laptop.box
                    dx, dy = (x2 - x1) * policy["crop_margin"], (y2 - y1) * policy["crop_margin"]
                    bounds = (
                        math.floor(max(0, x1 - dx) * w),
                        math.floor(max(0, y1 - dy) * h),
                        math.ceil(min(1, x2 + dx) * w),
                        math.ceil(min(1, y2 + dy) * h),
                    )
                    image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)).crop(bounds)
                    images.append(image)
                    sequence["samples"].append(
                        {
                            "target_t": t,
                            "decoded_t": actual,
                            "native_size": [w, h],
                            "native_crop_size": list(image.size),
                            "crop_box_pixels": bounds,
                            "frame_rgb_sha256": digest(
                                cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB).tobytes()
                            ),
                            "crop_rgb_sha256": digest(image.tobytes()),
                        }
                    )
                record["sequences"].append(sequence)
                if images:
                    jobs.append((record, sequence, images))
        finally:
            capture.release()
        record["prepare_sec"] = time.monotonic() - started
        records.append(record)
    return records, jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--videos", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if any(getattr(args, key) is None for key in ("base", "cache", "videos", "out")):
        parser.error("--base --cache --videos --out are required")
    policy_path = HERE / "manifest.json"
    policy = json.loads(policy_path.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    sources = {
        str(p.relative_to(args.base)): file_hash(p)
        for p in (
            args.base / "backend/f1/events.py",
            args.base / "backend/f1/calibration.py",
            args.base / "backend/f1/visual_checks.py",
            args.base / "config/perception.yaml",
            args.base / "config/overrides.yaml",
        )
    }
    metadata = {
        "policy_sha256": file_hash(policy_path),
        "runner_sha256": file_hash(Path(__file__)),
        "base_sources_sha256": sources,
        "status": "preparing",
    }
    records, jobs = prepare(args, policy)
    (args.out / "selection.json").write_text(json.dumps(records, indent=2))
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    if args.prepare_only:
        metadata["status"] = "CPU_PREPARED"
        (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
        print(
            json.dumps(
                {
                    "status": "CPU_PREPARED",
                    "cases": len(records),
                    "sequences": len(jobs),
                    "samples": sum(len(j[2]) for j in jobs),
                }
            )
        )
        return
    if args.model is None:
        parser.error("--model is required for local GPU inference")
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        RULE_SCOPE="detector",
    )
    import torch
    import transformers
    from backend.f1.visual_checks import model_identity
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_unavailable: use orchestrator argv outside sandbox")
    metadata.update(
        model=model_identity(args.model),
        model_revision=json.loads((args.model / "config.json").read_text()).get(
            "_commit_hash", "unknown_local_revision"
        ),
        torch=torch.__version__,
        transformers=transformers.__version__,
        status="model_loading",
    )
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    started = time.monotonic()
    torch.set_num_threads(4)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(args.model),
        dtype=torch.bfloat16,
        device_map="cuda",
        attn_implementation="sdpa",
        local_files_only=True,
    ).eval()
    processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
    metadata["model_load_sec"] = time.monotonic() - started
    deadline = time.monotonic() + policy["inference_budget_sec"]
    for record, sequence, images in jobs:
        started = time.monotonic()
        answers = ["unknown"] * len(images)
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError("pilot_budget_exhausted")
            prompt = policy["prompt"]
            content = [{"type": "image"} for _ in images] + [{"type": "text", "text": prompt}]
            text = processor.apply_chat_template(
                [{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True
            )
            inputs = processor(
                text=[text],
                images=images,
                size={"shortest_edge": policy["min_pixels"], "longest_edge": policy["max_pixels"]},
                return_tensors="pt",
            ).to(model.device)
            inputs.pop("token_type_ids", None)
            sequence["model_pixel_values_shape"] = list(inputs["pixel_values"].shape)
            sequence["model_image_grid_thw"] = inputs["image_grid_thw"].cpu().tolist()
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=policy["max_new_tokens"],
                    do_sample=False,
                    max_time=min(
                        policy["request_budget_sec"], max(0.1, deadline - time.monotonic())
                    ),
                )
            torch.cuda.synchronize()
            raw = processor.batch_decode(
                output[:, inputs["input_ids"].shape[1] :],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0].strip()
            sequence["raw"] = raw
            answers = parse_states(raw, len(images))
            sequence["status"] = "answered"
        except Exception as exc:
            sequence.update(status="unknown_error", error=type(exc).__name__)
        sequence["states"] = [
            {"t": sample["decoded_t"], "state": answer}
            for sample, answer in zip(sequence["samples"], answers, strict=True)
        ]
        sequence["transitions"] = [
            {"from_t": a["t"], "to_t": b["t"], "from": a["state"], "to": b["state"]}
            for a, b in zip(sequence["states"], sequence["states"][1:], strict=False)
            if a["state"] != "unknown" and b["state"] != "unknown" and a["state"] != b["state"]
        ]
        sequence["inference_sec"] = time.monotonic() - started
        record["inference_sec"] = sum(s.get("inference_sec", 0) for s in record["sequences"])
        (args.out / "results.json").write_text(json.dumps(records, indent=2))
        print(
            json.dumps(
                {
                    "evaluation_input": record["evaluation_input"],
                    "exit_t": sequence["exit"]["timestamp_sec"],
                    "status": sequence["status"],
                    "states": sequence["states"],
                    "sec": sequence["inference_sec"],
                }
            ),
            flush=True,
        )
    metadata.update(
        status="complete",
        sequences=len(jobs),
        unknown_samples=sum(
            s["state"] == "unknown"
            for r in records
            for seq in r["sequences"]
            for s in seq.get("states", [])
        ),
    )
    (args.out / "results.json").write_text(json.dumps(records, indent=2))
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
