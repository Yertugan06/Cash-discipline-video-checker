"""A20 spike: can door and laptop-screen states be read better than CLIP B-32 does now?

Ground truth is the team sheet's description of a few clips (intervals below). For each sampled
moment it crops the calibrated door / laptop box from the source frame and asks:
- CLIP B-32 (the deployed state model) with the deployed prompts and with alternative prompts;
- Qwen2.5-VL-7B-Instruct with a one-word question, on the crop and (door) on the full frame.
Prints one JSON line per (clip, time, family) with every method's answer. No images are saved.

Runs on datathon inside the checker image (GPU, local weights, no network):

    docker run --rm --gpus all --entrypoint '' -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
      --volumes-from datathon26-checker-1 -v ~/.cache/huggingface/hub:/hub:ro \
      -e QWEN=/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/<rev> \
      -v ~/data/open/videos:/videos:ro -v ~/a20-spike:/spike -w /spike \
      forte-cash-checker:cuda python states_spike.py > states.jsonl
"""

import glob
import json
import os
import re
import subprocess
import time
from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from transformers import (
    AutoProcessor,
    CLIPModel,
    CLIPProcessor,
    Qwen2_5_VLForConditionalGeneration,
)

CACHE = Path("/app/runtime/perception_cache")
VIDEOS = Path("/videos")
WEIGHTS = Path("/app/weights/states")
SAMPLES_PER_INTERVAL = 6

# (clip, family, expected, t_from, t_to), from data/Таблица_нарушений.xlsx
GROUND_TRUTH = [
    ("X-31", "door", "open", 0.5, 7.5),
    ("X-31", "door", "closed", 10, 30),
    ("X-30", "door", "open", 6, 20),
    ("X-32", "door", "open", 6, 20),
    ("X-33", "door", "open", 7, 14),
    ("X-11", "laptop", "working", 14, 24),
    ("X-28", "laptop", "working", 8, 20),
    ("X-29", "laptop", "locked", 7, 20),
    ("X-23", "laptop", "locked", 6, 14),
    ("X-22", "laptop", "locked", 6, 14),
    ("X-12", "laptop", "off", 17, 34),
]

CLIP_PROMPTS = {
    "deployed": {
        "door": {
            "open": ["a photo of an open glass door", "a doorway with its door open"],
            "closed": ["a photo of a shut glass door", "a closed door"],
        },
        "laptop": {
            "working": [
                "a laptop screen showing a working application",
                "a laptop screen with windows and documents",
            ],
            "locked": [
                "a laptop screen showing a login password screen",
                "a laptop showing a lock screen",
            ],
            "off": ["a closed laptop with its lid shut", "a laptop with a dark blank screen"],
        },
    },
    "alt": {
        "door": {
            "open": [
                "a glass door standing ajar with a gap at its edge",
                "an open door leading out of a small office",
                "a door swung open into the room",
            ],
            "closed": [
                "a glass door shut flush in its frame",
                "a closed glass door of a small office",
                "a door closed against its frame",
            ],
        },
        "laptop": {
            "working": [
                "a bright laptop screen with a spreadsheet",
                "a laptop displaying an open program with text",
                "a lit computer screen with windows",
            ],
            "locked": [
                "a laptop lock screen with a large clock and a wallpaper",
                "a computer login screen with a password box",
                "a laptop screen showing only a photo wallpaper",
            ],
            "off": [
                "a black laptop screen that is switched off",
                "a laptop with its lid closed",
                "a dark computer screen",
            ],
        },
    },
}

QUESTIONS = {
    "door": "This crop from a CCTV camera in a bank cash room shows the room's door (often a "
    "glass door). Is the door open or closed? Answer with one word: open, closed, or unsure.",
    "door_full": "This is a CCTV frame of a small bank cash room with a cash desk. Look at the "
    "door of the room (often a glass door). Is it open or closed right now? Answer with one "
    "word: open, closed, or unsure.",
    "laptop": "This crop from a CCTV camera shows a laptop on a cash desk. What does its screen "
    "show? Answer with one word: working (an application, documents or a spreadsheet), locked (a "
    "lock or login screen, or only wallpaper), off (dark screen or lid closed), or unsure.",
}


def clip_index() -> dict[str, tuple[str, Path]]:
    rows = [json.loads(line) for line in open("/spike/videos.jsonl") if line.strip()]
    return {
        r["original_id"].replace("Х", "X"): (r["sha256"], VIDEOS / Path(r["path"]).name)
        for r in rows
    }


def frame_at(video: Path, timestamp: float) -> Image.Image:
    data = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    if not data:
        raise ValueError(f"no frame at {timestamp} s")  # past the end of the clip
    return Image.open(BytesIO(data)).convert("RGB")


def crop(image: Image.Image, box, margin: float = 0.25) -> Image.Image:
    w, h = image.size
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * margin, (y2 - y1) * margin
    return image.crop(
        (
            int(max(0, x1 - px) * w),
            int(max(0, y1 - py) * h),
            int(min(1, x2 + px) * w),
            int(min(1, y2 + py) * h),
        )
    )


class Clip:
    def __init__(self):
        self.model = CLIPModel.from_pretrained(WEIGHTS, local_files_only=True).cuda().eval()
        self.processor = CLIPProcessor.from_pretrained(WEIGHTS, local_files_only=True)
        self.text = {}

    @torch.inference_mode()
    def __call__(self, image: Image.Image, prompts: dict[str, list[str]]) -> tuple[str, float]:
        key = json.dumps(prompts)
        if key not in self.text:
            flat = [p for group in prompts.values() for p in group]
            inputs = self.processor(text=flat, padding=True, return_tensors="pt").to("cuda")
            features = self.model.get_text_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
            protos, offset = [], 0
            for group in prompts.values():
                protos.append(features[offset : offset + len(group)].mean(0))
                offset += len(group)
            protos = torch.stack(protos)
            self.text[key] = protos / protos.norm(dim=-1, keepdim=True)
        pixels = self.processor.image_processor(
            images=image,
            size={"height": 224, "width": 224},
            do_center_crop=False,
            return_tensors="pt",
        ).to("cuda")
        image_features = self.model.get_image_features(**pixels)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        scores = (self.model.logit_scale.exp() * image_features @ self.text[key].T).softmax(-1)[0]
        best = int(scores.argmax())
        return list(prompts)[best], round(float(scores[best]), 3)


class Qwen:
    def __init__(self):
        path = os.environ["QWEN"]
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            path, torch_dtype=torch.bfloat16, local_files_only=True
        ).cuda().eval()
        self.processor = AutoProcessor.from_pretrained(
            path, local_files_only=True, min_pixels=128 * 28 * 28, max_pixels=640 * 28 * 28
        )

    @torch.inference_mode()
    def __call__(self, image: Image.Image, question: str) -> str:
        messages = [
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": question}]}
        ]
        text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[image], return_tensors="pt").to("cuda")
        output = self.model.generate(**inputs, max_new_tokens=4, do_sample=False)
        answer = self.processor.batch_decode(
            output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )[0]
        words = re.findall(r"[a-z]+", answer.lower())
        return words[0] if words else ""


def main() -> None:
    index = clip_index()
    clip, qwen = Clip(), Qwen()
    for name, family, expected, start, end in GROUND_TRUTH:
        sha, video = index[name]
        cache = max(glob.glob(str(CACHE / sha / "*.json")), key=os.path.getmtime)
        scene = json.load(open(cache))["scene"]
        obj = scene["objects"].get(family)
        step = (end - start) / max(SAMPLES_PER_INTERVAL - 1, 1)
        for i in range(SAMPLES_PER_INTERVAL):
            t = round(start + i * step, 2)
            row = {
                "clip": name,
                "family": family,
                "expected": expected,
                "t": t,
                "box": obj["box"] if obj else None,
            }
            try:
                frame = frame_at(video, t)
            except (subprocess.CalledProcessError, ValueError):
                continue
            if obj:
                piece = crop(frame, obj["box"])
                for variant, prompts in CLIP_PROMPTS.items():
                    row[f"clip_{variant}"] = clip(piece, prompts[family])
                started = time.monotonic()
                row["qwen_crop"] = qwen(piece, QUESTIONS[family])
                row["qwen_crop_s"] = round(time.monotonic() - started, 2)
            if family == "door":
                row["qwen_full"] = qwen(frame, QUESTIONS["door_full"])
            print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
