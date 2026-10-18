"""Frozen six-case offline temporal safe-action pilot. No production hook or labels.

Reuses A21's native decoder and the working Qwen3-VL offline loader/template path.
Only numeric/text metadata and model answers are saved; images remain in memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

ACTIONS = {"safe_handling", "table_counter_work", "unknown"}
DOORS = {"open", "closed", "unknown"}


def parse_answer(raw: str) -> dict:
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate output keys")
        return result

    answer = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(answer, dict) or set(answer) != {"samples"}:
        raise ValueError("expected only samples")
    rows = answer["samples"]
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("expected three ordered sample answers")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"action", "safe_door"}:
            raise ValueError("invalid sample fields")
        if not isinstance(row["action"], str) or row["action"] not in ACTIONS:
            raise ValueError("invalid action")
        if not isinstance(row["safe_door"], str) or row["safe_door"] not in DOORS:
            raise ValueError("invalid safe door state")
    return answer


def select_episode(events: list[dict], samples: list[dict], departures: list[float]) -> dict:
    """First stable counter episode after a safe candidate, with one visible cashier."""
    by_t = {sample["timestamp_sec"]: sample for sample in samples}
    candidates = [
        (e["timestamp_sec"], e["type"], e["facts"].get("actor_id", ""))
        for e in events
        if e["type"] in {"HAND_ON_SAFE", "SAFE_OPEN"}
    ]
    candidates += [(t, "safe_departure", "") for t in departures]
    for episode in sorted(
        (e for e in events if e["type"] == "COUNT_START"), key=lambda e: e["timestamp_sec"]
    ):
        t = episode["timestamp_sec"]
        selected = [by_t.get(t + offset) for offset in (0, 0.5, 1)]
        if any(s is None for s in selected):
            continue
        if any(s["states"].get("counter", {}).get("value") != "running" for s in selected):
            continue
        cashiers = [
            [
                d["track_id"]
                for d in s["detections"]
                if d["label"] == "person" and d["role"] == "cashier"
            ]
            for s in selected
        ]
        if any(len(ids) != 1 for ids in cashiers) or len({ids[0] for ids in cashiers}) != 1:
            continue
        actor = cashiers[0][0]
        prior = [c for c in candidates if c[0] < t and (not c[2] or c[2] == actor)]
        if prior:
            trigger = max(prior)
            return {
                "status": "selected",
                "times": [t, t + 0.5, t + 1],
                "actor_id": actor,
                "trigger_t": trigger[0],
                "trigger": trigger[1],
                "samples": selected,
            }
    return {
        "status": "no_trigger",
        "reason": "no_stable_counter_after_safe_candidate_with_visible_cashier",
    }


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def self_check() -> None:
    samples = [
        {
            "timestamp_sec": t,
            "states": {"counter": {"value": "running"}},
            "detections": [{"label": "person", "role": "cashier", "track_id": "p"}],
        }
        for t in (2, 2.5, 3)
    ]
    events = [
        {"timestamp_sec": 1, "type": "HAND_ON_SAFE", "facts": {"actor_id": "p"}},
        {"timestamp_sec": 2, "type": "COUNT_START", "facts": {}},
    ]
    assert select_episode(events, samples, [])["times"] == [2, 2.5, 3]
    assert select_episode(events[1:], samples, [])["status"] == "no_trigger"
    assert select_episode(events, samples[:2], [])["status"] == "no_trigger"
    answer = {"samples": [{"action": "unknown", "safe_door": "unknown"}] * 3}
    assert parse_answer(json.dumps(answer)) == answer
    try:
        parse_answer('{"samples":[],"confidence":99}')
    except ValueError:
        pass
    else:
        raise AssertionError("extra confidence output was accepted")
    print("selection/parser self-check passed; no model or pixels used")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--videos", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    if any(getattr(args, key) is None for key in ("base", "cache", "videos", "model", "out")):
        parser.error("base/cache/videos/model/out are required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    sys.path.insert(0, str(args.base.resolve()))
    sys.path.insert(0, str(args.base / "attempts/A21-deadline/recognition"))
    import compare_objects as common

    from backend.f1.calibration import calibrate
    from backend.f1.events import build_events
    from backend.f1.perception import load_perception_config
    from backend.f1.vision_types import Observation, Scene
    from backend.f1.visual_checks import _error_diagnostic, plan_checks

    manifest_path = Path(__file__).with_name("manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) > 6:
        raise ValueError("frozen maximum six cases")
    config = load_perception_config(args.base / "config/perception.yaml")
    records = []
    args.out.mkdir(parents=True, exist_ok=True)
    for clip in manifest["cases"]:
        record = {
            "case": clip,
            "status": "unknown",
            "answer": {
                "samples": [{"action": "unknown", "safe_door": "unknown"} for _ in range(3)]
            },
        }
        records.append(record)
        try:
            video = common.find_video(args.videos, clip)
            checksum = digest(video)
            cache = max((args.cache / checksum).glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
            payload = json.loads(cache.read_text())
            scene = Scene.model_validate(payload["scene"])
            if scene.candidates:
                scene = calibrate(scene.candidates, args.base / "config/overrides.yaml", checksum)
            observations = [Observation.model_validate(o) for o in payload["observations"]]
            duration = observations[-1].timestamp_sec + 0.5
            log = build_events(scene, observations, config, 2, duration)
            requests = plan_checks(scene, log, observations, duration, families=("safe",))
            departures = sorted({r.trigger_t for r in requests if r.trigger == "safe_departure"})
            selection = select_episode(
                [e.model_dump() for e in log.events],
                [o.model_dump() for o in observations],
                departures,
            )
            record.update(
                video=str(video),
                video_sha256=checksum,
                cache_sha256=digest(cache),
                selection=selection,
                scene=scene.model_dump(),
                role_coverage=log.coverage.get("roles"),
                status=selection["status"],
            )
            record["cv_event_candidates"] = [
                e.model_dump()
                for e in log.events
                if e.type in {"HAND_ON_SAFE", "SAFE_OPEN", "COUNT_START", "COUNT_END"}
            ]
            record["cv_counter_timeline"] = [
                {
                    "t": o.timestamp_sec,
                    "state": o.states["counter"].model_dump() if "counter" in o.states else None,
                    "cashiers": [
                        d.track_id
                        for d in o.detections
                        if d.label == "person" and d.role == "cashier"
                    ],
                }
                for o in observations
            ]
            safe = scene.objects.get("safe")
            if not safe or not (
                0 <= safe.box[0] < safe.box[2] <= 1 and 0 <= safe.box[1] < safe.box[3] <= 1
            ):
                record.update(status="unknown", error="missing_or_invalid_safe_calibration")
            elif not log.coverage.get("roles"):
                record.update(status="no_trigger", error="role_coverage_unknown")
            elif selection["status"] == "selected":
                record["safe_box"] = list(safe.box)
        except (OSError, ValueError, RuntimeError) as exc:
            record.update(error=_error_diagnostic(exc, "numeric_selection"))
    metadata = {
        "manifest_sha256": digest(manifest_path),
        "script_sha256": digest(Path(__file__)),
        "base": str(args.base),
        "status": "planned",
        "model": str(args.model),
        "worker_python": sys.executable,
        "images_leave_vm": False,
        "labels_used_by_selector_or_model": False,
    }
    common.write_json(args.out / "cv-selection.json", records)
    common.write_json(args.out / "metadata.json", metadata)
    if args.plan_only:
        print(
            json.dumps(
                {
                    "status": "planned",
                    "cases": [
                        {
                            "case": r["case"],
                            "status": r["status"],
                            "times": r.get("selection", {}).get("times"),
                        }
                        for r in records
                    ],
                }
            )
        )
        return 0
    started = time.monotonic()
    try:
        import torch
        import transformers
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; orchestrator must run this pilot outside sandbox")
        torch.set_num_threads(2)
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(args.model),
            dtype=torch.bfloat16,
            device_map="cuda",
            attn_implementation="sdpa",
            local_files_only=True,
        ).eval()
        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
        metadata.update(
            load_s=time.monotonic() - started,
            torch=torch.__version__,
            transformers=transformers.__version__,
            config_sha256=digest(args.model / "config.json"),
            weights=[
                {"file": p.name, "bytes": p.stat().st_size}
                for p in args.model.glob("*.safetensors")
            ],
        )
    except Exception as exc:
        metadata.update(status="model_unavailable", error=_error_diagnostic(exc, "load"))
        common.write_json(args.out / "metadata.json", metadata)
        return 2
    deadline = time.monotonic() + manifest["inference_budget_s"]
    for record in records:
        if record["status"] != "selected":
            continue
        started = time.monotonic()
        try:
            if started >= deadline:
                raise TimeoutError("pilot inference budget expired")
            images, samples = [], []
            for t in record["selection"]["times"]:
                full, sample = common.grab_frame(Path(record["video"]), t)
                if abs(sample["decoded_t"] - t) > 0.25:
                    raise ValueError("decoded frame is too far from the selected sample")
                x1, y1, x2, y2 = record["safe_box"]
                dx, dy = (
                    (x2 - x1) * manifest["safe_crop_margin"],
                    (y2 - y1) * manifest["safe_crop_margin"],
                )
                w, h = full.size
                box = (
                    math.floor(max(0, x1 - dx) * w),
                    math.floor(max(0, y1 - dy) * h),
                    math.ceil(min(1, x2 + dx) * w),
                    math.ceil(min(1, y2 + dy) * h),
                )
                crop = full.crop(box)
                sample.update(
                    full_rgb_sha256=hashlib.sha256(full.tobytes()).hexdigest(),
                    safe_crop_rgb_sha256=hashlib.sha256(crop.tobytes()).hexdigest(),
                    safe_crop_box_px=list(box),
                    safe_crop_size_wh=list(crop.size),
                )
                samples.append(sample)
                images.extend([full, crop])
            record["frames"] = samples
            if len({s["frame_index_after_read"] for s in samples}) != 3:
                raise ValueError("decoder reused the same frame across ordered samples")
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "image"} for _ in images]
                    + [{"type": "text", "text": manifest["prompt"]}],
                }
            ]
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = processor(
                text=[text], images=images, size=manifest["processor_size"], return_tensors="pt"
            ).to(model.device)
            inputs.pop("token_type_ids", None)
            with torch.inference_mode():
                result = model.generate(
                    **inputs,
                    max_new_tokens=manifest["max_new_tokens"],
                    do_sample=False,
                    max_time=min(manifest["max_call_s"], max(0, deadline - time.monotonic())),
                )
            torch.cuda.synchronize()
            raw = processor.batch_decode(
                result[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
            )[0].strip()
            record.update(
                raw=raw,
                input_tokens=int(inputs["input_ids"].shape[1]),
                image_grid_thw=inputs["image_grid_thw"].detach().cpu().tolist(),
            )
            record.update(answer=parse_answer(raw), status="answered")
        except Exception as exc:
            record.update(status="unknown", error=_error_diagnostic(exc, "temporal_relation"))
        record["elapsed_s"] = round(time.monotonic() - started, 3)
        common.write_json(args.out / "results.json", records)
        print(
            json.dumps(
                {
                    "case": record["case"],
                    "status": record["status"],
                    "elapsed_s": record["elapsed_s"],
                }
            ),
            flush=True,
        )
    metadata.update(
        status="finished",
        inference_elapsed_s=round(time.monotonic() - deadline + manifest["inference_budget_s"], 3),
    )
    common.write_json(args.out / "results.json", records)
    common.write_json(args.out / "metadata.json", metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
