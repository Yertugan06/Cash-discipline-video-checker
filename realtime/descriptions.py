"""Local video descriptions for a human to correct; never checker inputs or truth labels.

Run on a GPU VM with the existing inference environment::

    python -m realtime.descriptions --videos /path/to/videos \
        --output runtime/realtime/descriptions --model /local/Qwen3-VL-4B-Instruct --first X-2

Only this optional worker imports the ML dependencies. Drafts and human annotations
are separate files, so rerunning the worker cannot overwrite a person's corrections.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROMPT_VERSION = 1
PROMPT = """These are chronological frames sampled across one bank service video.
Write a short factual draft of what happens, for a person to correct while watching.
Use plain English, in chronological order: 4-8 short sentences, each on a new line.
Describe the people's visible actions and interactions, including arrivals/departures,
exchanging or handling objects, counting, and door/safe activity ONLY when visible.
Identify the cashier and client only if their positions/actions support those roles.
Distinguish cash, cards, documents, and machines only when clearly recognizable.
Otherwise say "small object" or briefly state what is unclear. Do not invent actions
between sampled frames. Omit routine background details and repetitive movements.
No timestamps, title, introduction, money amounts, laws, or violation judgments.
The draft must be specific to the visible sequence, not a generic banking scenario.
"""


class DescriptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    clip: str = Field(pattern=r"^X-\d+$")
    status: Literal["unavailable", "queued", "processing", "ready", "failed"]
    description: str = Field(default="", max_length=6000)
    model: str = Field(default="", max_length=120)
    prompt_version: int = PROMPT_VERSION
    video_sha256: str = Field(default="", max_length=64)
    duration_sec: float | None = Field(default=None, ge=0)
    sampled_timestamps: list[float] = Field(default_factory=list, max_length=96)
    generated_at: float | None = Field(default=None, ge=0)
    error: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def valid_result(self) -> DescriptionDraft:
        if self.status == "ready" and (
            not self.description.strip() or not self.model or not self.sampled_timestamps
        ):
            raise ValueError("a ready draft needs text, a model, and sampled frame times")
        if self.status == "failed" and not self.error:
            raise ValueError("a failed draft needs an explicit error")
        if any(not math.isfinite(t) or t < 0 for t in self.sampled_timestamps):
            raise ValueError("sample times must be finite and nonnegative")
        return self


def write_draft(directory: Path, draft: DescriptionDraft) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{draft.clip}.json"
    partial = path.with_suffix(".partial")
    partial.write_text(draft.model_dump_json(indent=1), encoding="utf-8")
    partial.replace(path)


def sample_video(path: Path, *, max_frames: int = 64, short_side: int = 384):
    """Sample the whole clip using presentation times, including variable-rate video."""
    import av
    import numpy as np
    import torch

    images, timestamps = [], []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        duration = (
            float(stream.duration * stream.time_base)
            if stream.duration is not None
            else float(container.duration or 0) / av.time_base
        )
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("video has no valid duration")
        fps = float(stream.average_rate or 25)
        count = max(4, min(max_frames, math.ceil(duration)))
        targets = np.linspace(0, max(0, duration - 1 / fps), count)
        start = float((stream.start_time or 0) * stream.time_base)
        next_index = 0
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            timestamp = max(0, float(frame.pts * stream.time_base) - start)
            if timestamp + 1e-6 < targets[next_index]:
                continue
            image = frame.to_image()
            width, height = image.size
            scale = short_side / min(width, height)
            size = tuple(max(32, round(d * scale / 32) * 32) for d in image.size)
            images.append(np.asarray(image.resize(size), dtype=np.uint8).transpose(2, 0, 1))
            timestamps.append(timestamp)
            next_index += 1
            while next_index < count and targets[next_index] <= timestamp:
                next_index += 1
            if next_index == count:
                break
    if not images:
        raise ValueError("video decoded no frames")
    while len(images) < 4 or len(images) % 2:
        images.append(images[-1])
        timestamps.append(timestamps[-1])
    metadata = {
        "fps": fps,
        "frames_indices": [round(t * fps) for t in timestamps],
        "total_num_frames": max(round(duration * fps), round(timestamps[-1] * fps) + 1),
        "duration": duration,
    }
    return torch.from_numpy(np.stack(images)), timestamps, metadata


def generate_description(model, processor, video, metadata) -> str:
    import torch

    messages = [{"role": "user", "content": [{"type": "video"}, {"type": "text", "text": PROMPT}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(
        text=[text],
        videos=[video],
        video_metadata=[metadata],
        do_sample_frames=False,
        do_resize=False,
        return_tensors="pt",
    ).to(model.device)
    inputs.pop("token_type_ids", None)
    with torch.inference_mode():
        result = model.generate(**inputs, max_new_tokens=420, do_sample=False)
    description = processor.batch_decode(
        result[:, inputs["input_ids"].shape[1] :],
        skip_special_tokens=True,
    )[0].strip()
    if not description or len(description) > 6000:
        raise ValueError("model did not produce a usable description")
    return description


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--first", default="X-2")
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    model_name = args.model.name
    jobs = []
    for path in args.videos.iterdir():
        match = re.fullmatch(r"[XxХх]\s*-?\s*(\d+)", path.stem)
        if path.is_file() and path.suffix.lower() in {".mov", ".mp4"} and match:
            jobs.append((f"X-{int(match[1])}", path))
    jobs.sort(key=lambda job: (job[0] != args.first, job[0] == "X-1", int(job[0][2:])))
    pending, by_hash = [], {}
    for clip, path in jobs:
        saved = args.output / f"{clip}.json"
        if saved.exists():
            draft = DescriptionDraft.model_validate_json(saved.read_text(encoding="utf-8"))
            if (
                draft.status == "ready"
                and draft.model == model_name
                and draft.prompt_version == PROMPT_VERSION
            ):
                by_hash[draft.video_sha256] = draft
                continue
        write_draft(args.output, DescriptionDraft(clip=clip, status="queued", model=model_name))
        pending.append((clip, path))
    if not pending:
        print(json.dumps({"status": "complete", "generated": 0}), flush=True)
        return
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    try:
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(args.model),
            dtype=torch.bfloat16,
            device_map="cuda",
            attn_implementation="sdpa",
            local_files_only=True,
        ).eval()
        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True)
    except Exception as error:
        for clip, _ in pending:
            write_draft(
                args.output,
                DescriptionDraft(
                    clip=clip,
                    status="failed",
                    model=model_name,
                    error=f"Model startup failed: {type(error).__name__}: {error}"[:500],
                ),
            )
        raise
    print(json.dumps({"status": "model_loaded", "pending": len(pending)}), flush=True)
    for clip, path in pending:
        started = time.monotonic()
        draft = DescriptionDraft(clip=clip, status="processing", model=model_name)
        write_draft(args.output, draft)
        try:
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest in by_hash:
                draft = by_hash[digest].model_copy(update={"clip": clip})
            else:
                video, timestamps, metadata = sample_video(path)
                description = generate_description(model, processor, video, metadata)
                draft = DescriptionDraft(
                    clip=clip,
                    status="ready",
                    description=description,
                    model=model_name,
                    video_sha256=digest,
                    duration_sec=metadata["duration"],
                    sampled_timestamps=timestamps,
                    generated_at=time.time(),
                )
                by_hash[digest] = draft
        except Exception as error:
            torch.cuda.empty_cache()
            draft = DescriptionDraft(
                clip=clip,
                status="failed",
                model=model_name,
                error=f"{type(error).__name__}: {error}"[:500],
            )
        write_draft(args.output, draft)
        print(
            json.dumps(
                {
                    "clip": clip,
                    "status": draft.status,
                    "seconds": round(time.monotonic() - started, 1),
                    "frames": len(draft.sampled_timestamps),
                    "error": draft.error,
                }
            ),
            flush=True,
        )
    print(json.dumps({"status": "complete"}), flush=True)


if __name__ == "__main__":
    main()
