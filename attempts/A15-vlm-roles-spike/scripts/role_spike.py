"""A15 spike: can a local VLM tell each detected person's role and the room situation?

For each clip: take the run-3 trace, split the clip into 4 segments, pick the frame with the most
person boxes in each, draw numbered boxes (glass-filtered ones too, so we see whether the VLM
spots reflections) and ask Qwen2.5-VL-7B-Instruct for per-person role/action and the situation.

Runs inside the checker image on datathon (GPU, local weights, no network):

    docker run --rm --gpus all --entrypoint '' -e HF_HUB_OFFLINE=1 \
      -v ~/.cache/huggingface/hub:/hub:ro \
      -e MODEL_DIR=/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/<rev> \
      -v datathon26_work:/app/runtime:ro -v ~/data/open/videos:/videos:ro \
      -v /tmp/a15:/out -v $PWD/attempts/A15-vlm-roles-spike/scripts:/spike:ro \
      forte-cash-checker:cuda python /spike/role_spike.py
"""

import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

import torch
from PIL import Image, ImageDraw, ImageFont
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

MODEL = Path(os.environ["MODEL_DIR"])  # snapshot dir; files link into the hub blobs
TRACES = Path("/app/runtime/traces")
VIDEOS = Path("/videos")
OUT = Path("/out")
SEGMENTS = 4

PROMPT = """This is one frame from a fixed CCTV camera inside a bank cash room: a small office \
with one cash desk, a laptop, a banknote counting machine and a metal safe. One wall and the \
door are glass, so the glass can show reflections of people in the room, and people walking \
outside the room can be seen through it.

Numbered red boxes mark detected people. For EVERY numbered box decide:
- role: "cashier" (bank employee working at the cash desk), "client" (customer being served), \
"collector" (cash-collection staff, usually bringing or taking a cash bag), "other_staff", or \
"outside_or_reflection" (a reflection in the glass, or a person outside the room behind the glass)
- action: one of "working_at_desk", "serving_client", "handing_over_item", "counting_cash", \
"carrying_bag", "walking", "standing", "sitting", "none"

Also classify the whole scene as one situation: "client_service" (a client is being served), \
"cash_collection" (a collector brings or takes a cash bag), "walk_through" (someone walks \
in or around without being served), "cashier_alone", or "other".

Answer with JSON only, no other text:
{"situation": "...", "people": [{"id": 1, "role": "...", "action": "...", "reason": "few words"}]}"""


def pick_frames(trace: dict) -> list[dict]:
    frames = [f for f in trace["frames"] if any(d[0] == "person" for d in f["dets"])]
    if not frames:
        return []
    picked = []
    size = max(1, len(frames) // SEGMENTS)
    for start in range(0, len(frames), size):
        segment = frames[start : start + size]
        best = max(segment, key=lambda f: sum(d[0] == "person" for d in f["dets"]))
        if best not in picked:
            picked.append(best)
    return picked[:SEGMENTS]


def grab(video: Path, t: float) -> Image.Image:
    jpeg = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
         "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
        capture_output=True, check=True,
    ).stdout
    return Image.open(io.BytesIO(jpeg)).convert("RGB")


def mark(image: Image.Image, people: list[list]) -> Image.Image:
    image = image.copy()
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(16, image.width // 24))
    w, h = image.size
    for number, det in enumerate(people, 1):
        _, _, _, x1, y1, x2, y2, _ = det
        box = (x1 * w, y1 * h, x2 * w, y2 * h)
        draw.rectangle(box, outline=(255, 0, 0), width=3)
        tag = str(number)
        tw = draw.textlength(tag, font=font)
        draw.rectangle((box[0], box[1], box[0] + tw + 8, box[1] + font.size + 6), fill=(255, 0, 0))
        draw.text((box[0] + 4, box[1] + 2), tag, fill=(255, 255, 255), font=font)
    return image


def ask(model, processor, image: Image.Image) -> tuple[str, float]:
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt").to(model.device)
    start = time.monotonic()
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=400, do_sample=False)
    answer = processor.batch_decode(
        output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
    )[0]
    return answer, time.monotonic() - start


def parse(answer: str) -> dict | None:
    match = re.search(r"\{.*\}", answer, re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None


def main() -> None:
    clips = json.loads((Path(__file__).parent / "clips.json").read_text(encoding="utf-8"))
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL, dtype=torch.bfloat16, attn_implementation="sdpa"
    ).to("cuda")
    processor = AutoProcessor.from_pretrained(MODEL)
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    with (OUT / "results.jsonl").open("w", encoding="utf-8") as results:
        for clip in clips:
            trace = json.loads((TRACES / f"{clip['job_id']}.json").read_text(encoding="utf-8"))
            for frame in pick_frames(trace):
                people = [d for d in frame["dets"] if d[0] == "person"]
                image = mark(grab(VIDEOS / clip["clip"], frame["t"]), people)
                name = f"x{clip['n']:02d}_{frame['t']:05.1f}.jpg"
                image.save(OUT / "img" / name, quality=90)
                answer, seconds = ask(model, processor, image)
                row = {
                    "clip": clip["clip"], "t": frame["t"], "image": name,
                    "f1_roles": [d[2] for d in people],
                    "boxes": [[round(v, 3) for v in d[3:7]] for d in people],
                    "vlm": parse(answer), "raw": answer, "seconds": round(seconds, 2),
                }
                results.write(json.dumps(row, ensure_ascii=False) + "\n")
                results.flush()
                print(name, row["f1_roles"], "->", answer.replace("\n", " ")[:300], flush=True)
    print("peak GPU GB", round(torch.cuda.max_memory_allocated() / 1e9, 1))


if __name__ == "__main__":
    main()
