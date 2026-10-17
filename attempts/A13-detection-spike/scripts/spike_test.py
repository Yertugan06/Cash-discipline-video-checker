#!/usr/bin/env python3
"""
Detection spike test for the ForteBank cash-discipline project.

Answers one question fast: can off-the-shelf open models see what our rules need
(cash on the desk, open safe, cash bag, ID card, cup/food, coat/handbag, laptop screen state)
in these top-down 464x848 clips?

Path A = open-vocabulary detectors (OWLv2, Grounding DINO).
Path B = vision-language model answering fixed yes/no questions (Qwen2.5-VL-7B-Instruct).

Setup (Ubuntu 22.04/24.04 or WSL2, NVIDIA GPU):
    python -m venv .venv && source .venv/bin/activate
    # RTX 50xx: use cu128. Older cards: cu121/cu124 also fine.
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install "transformers>=4.49" accelerate pillow opencv-python
    python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

Run:
    python spike_test.py --videos /path/to/videos --out spike_out              # OWLv2 + Grounding DINO
    python spike_test.py --videos /path/to/videos --out spike_out --models owl,gdino,vlm   # + Qwen2.5-VL (needs ~17 GB VRAM in bf16)
    python spike_test.py --videos /path/to/videos --out spike_out --models none   # only extract frames (sanity check)

Open spike_out/report.html. First run downloads weights from Hugging Face (needs internet once).
"""
import argparse, glob, html, json, os, re, time

import cv2
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Test frames. Expected values come from manual review of the clips.
# None / missing key = not scored for that frame.
# ---------------------------------------------------------------------------
FRAMES = [
    # clip, time_s, note, expected
    ("X-4", 56.0, "Client 1 cash left on desk, client 2 entering", {"cash": True, "safe_open": False}),
    ("X-38", 30.0, "Client 1 notes left on desk", {"cash": True}),
    ("X-26", 15.0, "Cashier gone, cash on desk", {"cash": True}),
    ("X-10", 8.0, "Cashier counting cash alone", {"cash": True}),
    ("X-2", 9.8, "Notes on desk, no ID shown", {"cash": True, "id_card": False}),
    ("X-1", 16.0, "ID card lying on desk", {"id_card": True}),
    ("X-13", 30.0, "Bundles on desk from opened bag", {"cash": True, "bag": True}),
    ("X-14", 60.0, "Recounting bundles", {"cash": True}),
    ("X-15", 17.0, "Packed cash bag left on desk", {"bag": True}),
    ("X-17", 6.0, "Collector carrying bag", {"bag": True}),
    ("X-20", 6.0, "Safe door wide open", {"safe_open": True}),
    ("X-23", 16.0, "Cashier leaving, desk clear, safe closed, laptop locked", {"cash": False, "safe_open": False, "screen": "locked"}),
    ("X-29", 16.0, "Laptop on lock screen", {"cash": False, "screen": "locked"}),
    ("X-28", 12.0, "Laptop unlocked, working app", {"screen": "working"}),
    ("X-11", 21.0, "Lights off, laptop unlocked (low light)", {"screen": "working"}),
    ("X-40", 18.0, "Coat and handbag on cash desk", {"coat_bag": True}),
    ("X-46", 13.0, "Cashier eating / drinking", {"food_cup": True}),
    ("X-24", 3.0, "Tablet + cup on desk", {"food_cup": True}),
    ("X-32", 2.0, "Empty room", {"cash": False, "safe_open": False, "coat_bag": False, "food_cup": False, "bag": False}),
    ("X-33", 2.0, "Empty room (other layout)", {"cash": False, "coat_bag": False, "food_cup": False, "bag": False}),
]

# Path A prompts per key. A key is "True" if any of its prompts is detected above threshold.
PROMPTS = {
    "cash": ["banknotes", "stack of paper money", "bundle of cash"],
    "bag": ["green fabric bag", "cash collection bag"],
    "id_card": ["id card", "plastic card"],
    "safe_open": ["open safe door", "open metal cabinet door"],
    "food_cup": ["cup", "drink bottle", "snack food"],
    "coat_bag": ["coat", "handbag"],
}
EXTRA_PROMPTS = ["person", "laptop", "money counting machine", "metal safe", "glass door"]  # context, not scored

# Path B questions (one call per frame, JSON answer).
VLM_QUESTION = (
    "This is a top-down security camera frame of a bank cashier's room. Answer ONLY with JSON, no prose:\n"
    '{"cash": true/false (paper money or banknote bundles visible anywhere on the desk or in hands),\n'
    ' "bag": true/false (a green fabric cash-collection bag is visible),\n'
    ' "id_card": true/false (a small ID card or plastic card lies on the desk),\n'
    ' "safe_open": true/false (the grey metal safe/cabinet door is open),\n'
    ' "food_cup": true/false (a cup, bottle or food is visible on the desk or in a hand),\n'
    ' "coat_bag": true/false (a coat or handbag lies on the desk),\n'
    ' "screen": "locked" | "working" | "closed" | "not_visible" (laptop screen: lock-screen wallpaper, an open application, lid closed),\n'
    ' "people": integer (number of people visible)}'
)

COLORS = {"cash": "#00c853", "bag": "#2962ff", "id_card": "#ff6d00", "safe_open": "#d50000",
          "food_cup": "#aa00ff", "coat_bag": "#c51162", "extra": "#9e9e9e"}


# ---------------------------------------------------------------------------
def find_video(videos_dir, clip):
    n = clip.split("-")[1]
    for path in glob.glob(os.path.join(videos_dir, "**", "*.mov"), recursive=True):
        stem = os.path.splitext(os.path.basename(path))[0]
        m = re.search(r"(\d+)$", stem)
        if m and m.group(1) == n:
            return path
    raise FileNotFoundError(f"No video for {clip} in {videos_dir}")


def grab(path, t):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read {path} at {t}s")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def key_of(label):
    for k, ps in PROMPTS.items():
        if label in ps:
            return k
    return "extra"


def draw(img, dets, title):
    im = img.copy()
    d = ImageDraw.Draw(im)
    for det in dets:
        x0, y0, x1, y1 = det["box"]
        c = COLORS[key_of(det["label"])]
        d.rectangle([x0, y0, x1, y1], outline=c, width=3)
        d.text((x0 + 3, max(0, y0 - 12)), f'{det["label"]} {det["score"]:.2f}', fill=c)
    d.rectangle([0, 0, im.width, 18], fill="black")
    d.text((4, 3), title, fill="white")
    return im


def to_bool(dets):
    found = {k: False for k in PROMPTS}
    for det in dets:
        k = key_of(det["label"])
        if k in found:
            found[k] = True
    return found


# ---------------------------------------------------------------------------
class Owl:
    name = "owl"

    def __init__(self, device, thr):
        from transformers import Owlv2Processor, Owlv2ForObjectDetection
        mid = "google/owlv2-base-patch16-ensemble"
        self.proc = Owlv2Processor.from_pretrained(mid)
        self.model = Owlv2ForObjectDetection.from_pretrained(mid).to(device).eval()
        self.device, self.thr = device, thr
        self.labels = [p for ps in PROMPTS.values() for p in ps] + EXTRA_PROMPTS

    def __call__(self, img):
        import torch
        inputs = self.proc(text=[self.labels], images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model(**inputs)
        side = max(img.size)  # OWLv2 pads to a square at bottom/right
        try:
            res = self.proc.post_process_grounded_object_detection(out, threshold=self.thr, target_sizes=[(side, side)])[0]
        except (AttributeError, TypeError):
            res = self.proc.post_process_object_detection(out, threshold=self.thr, target_sizes=[(side, side)])[0]
        return [{"label": self.labels[int(l)], "score": float(s), "box": [float(v) for v in b]}
                for s, l, b in zip(res["scores"], res["labels"], res["boxes"])]


class GDino:
    name = "gdino"

    def __init__(self, device, thr, text_thr):
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        mid = "IDEA-Research/grounding-dino-base"
        self.proc = AutoProcessor.from_pretrained(mid)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(mid).to(device).eval()
        self.device, self.thr, self.text_thr = device, thr, text_thr
        self.labels = [p for ps in PROMPTS.values() for p in ps] + EXTRA_PROMPTS

    def __call__(self, img):
        import torch
        text = ". ".join(self.labels) + "."
        inputs = self.proc(images=img, text=text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model(**inputs)
        kw = dict(text_threshold=self.text_thr, target_sizes=[img.size[::-1]])
        try:
            res = self.proc.post_process_grounded_object_detection(out, inputs.input_ids, threshold=self.thr, **kw)[0]
        except TypeError:  # older transformers
            res = self.proc.post_process_grounded_object_detection(out, inputs.input_ids, box_threshold=self.thr, **kw)[0]
        labels = res.get("text_labels", res.get("labels"))
        dets = []
        for s, l, b in zip(res["scores"], labels, res["boxes"]):
            l = str(l).strip()
            # map the returned phrase back to our closest prompt
            best = max(self.labels, key=lambda p: (p == l) * 10 + len(set(p.split()) & set(l.split())))
            dets.append({"label": best, "raw": l, "score": float(s), "box": [float(v) for v in b]})
        return dets


class Vlm:
    name = "vlm"

    def __init__(self, device):
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        mid = "Qwen/Qwen2.5-VL-7B-Instruct"  # check the licence of the checkpoint you use
        self.proc = AutoProcessor.from_pretrained(mid)
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            mid, torch_dtype=torch.bfloat16, device_map="auto").eval()

    def __call__(self, img):
        import torch
        msgs = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": VLM_QUESTION}]}]
        text = self.proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self.proc(text=[text], images=[img], return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=160, do_sample=False)
        raw = self.proc.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            ans = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            ans = {}
        return {"raw": raw, "answer": ans}


# ---------------------------------------------------------------------------
def score(expected, predicted):
    """Return list of (key, expected, predicted, correct)."""
    rows = []
    for k, e in expected.items():
        p = predicted.get(k)
        rows.append((k, e, p, None if p is None else (p == e)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True)
    ap.add_argument("--out", default="spike_out")
    ap.add_argument("--models", default="owl,gdino", help="comma list of owl,gdino,vlm or 'none'")
    ap.add_argument("--owl-thr", type=float, default=0.15)
    ap.add_argument("--gdino-thr", type=float, default=0.30)
    ap.add_argument("--gdino-text-thr", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(os.path.join(args.out, "img"), exist_ok=True)
    want = [] if args.models == "none" else [m.strip() for m in args.models.split(",")]

    device = "cpu"
    if want:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print("device:", device, torch.cuda.get_device_name(0) if device == "cuda" else "")

    models = []
    for m in want:
        t0 = time.time()
        if m == "owl":
            models.append(Owl(device, args.owl_thr))
        elif m == "gdino":
            models.append(GDino(device, args.gdino_thr, args.gdino_text_thr))
        elif m == "vlm":
            models.append(Vlm(device))
        print(f"loaded {m} in {time.time() - t0:.1f}s")

    results = []
    for clip, t, note, expected in FRAMES:
        img = grab(find_video(args.videos, clip), t)
        base = f"{clip}_{t:.1f}"
        img.save(os.path.join(args.out, "img", f"{base}_raw.jpg"), quality=90)
        rec = {"clip": clip, "t": t, "note": note, "expected": expected, "models": {}}
        for m in models:
            t0 = time.time()
            out = m(img)
            dt = time.time() - t0
            if m.name == "vlm":
                pred = out["answer"]
                rec["models"]["vlm"] = {"pred": pred, "raw": out["raw"], "sec": dt}
            else:
                pred = to_bool(out)
                draw(img, out, f"{m.name} {base}").save(os.path.join(args.out, "img", f"{base}_{m.name}.jpg"), quality=90)
                rec["models"][m.name] = {"pred": pred, "dets": out, "sec": dt}
            rec["models"][m.name]["score"] = score(expected, pred)
        results.append(rec)
        print(clip, t, {k: v["score"] for k, v in rec["models"].items()})

    with open(os.path.join(args.out, "results.json"), "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    write_report(args.out, results, [m.name for m in models])


def write_report(out, results, names):
    # summary per model per key
    summary = {}
    for n in names:
        for r in results:
            for k, e, p, ok in r["models"][n]["score"]:
                s = summary.setdefault(n, {}).setdefault(k, [0, 0])
                s[1] += 1
                s[0] += 1 if ok else 0
    timing = {n: sum(r["models"][n]["sec"] for r in results) / max(1, len(results)) for n in names}

    h = ["<!doctype html><meta charset='utf-8'><title>Detection spike</title>",
         "<style>body{font:14px Arial,sans-serif;margin:16px;background:#fff;color:#111}"
         "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top}"
         ".ok{background:#d7f5dd}.bad{background:#fbd5d5}img{max-width:300px;display:block}"
         "pre{white-space:pre-wrap;max-width:320px;font-size:11px}</style>",
         "<h1>Detection spike test</h1>"]
    if names:
        h.append("<h2>Accuracy per key (correct / scored)</h2><table><tr><th>Key</th>"
                 + "".join(f"<th>{n}</th>" for n in names) + "</tr>")
        for k in ["cash", "bag", "id_card", "safe_open", "food_cup", "coat_bag", "screen"]:
            h.append(f"<tr><td>{k}</td>" + "".join(
                f"<td>{summary.get(n, {}).get(k, [0, 0])[0]} / {summary.get(n, {}).get(k, [0, 0])[1]}</td>" for n in names) + "</tr>")
        h.append("<tr><td>sec / frame</td>" + "".join(f"<td>{timing[n]:.2f}</td>" for n in names) + "</tr></table>")
        h.append("<p>Path A models can't judge <b>screen</b>; it is scored for the VLM only. "
                 "Rule of thumb: a key needs ~90% here before a rule can rely on it.</p>")
    h.append("<h2>Frames</h2><table><tr><th>Frame</th><th>Expected</th>"
             + "".join(f"<th>{n}</th>" for n in names) + "</tr>")
    for r in results:
        base = f'{r["clip"]}_{r["t"]:.1f}'
        h.append(f"<tr><td><b>{r['clip']} @ {r['t']}s</b><br>{html.escape(r['note'])}<img src='img/{base}_raw.jpg'></td>")
        h.append("<td>" + "<br>".join(f"{k}: {v}" for k, v in r["expected"].items()) + "</td>")
        for n in names:
            m = r["models"][n]
            cells = "".join(f"<div class='{'ok' if ok else 'bad' if ok is False else ''}'>{k}: {p}</div>"
                            for k, e, p, ok in m["score"])
            pic = f"<img src='img/{base}_{n}.jpg'>" if n != "vlm" else f"<pre>{html.escape(m['raw'])}</pre>"
            h.append(f"<td>{cells}{pic}<small>{m['sec']:.2f}s</small></td>")
        h.append("</tr>")
    h.append("</table>")
    with open(os.path.join(out, "report.html"), "w") as f:
        f.write("\n".join(h))
    print("report:", os.path.join(out, "report.html"))


if __name__ == "__main__":
    main()
