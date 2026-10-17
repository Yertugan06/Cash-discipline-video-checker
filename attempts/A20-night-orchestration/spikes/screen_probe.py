"""A20 probe: does the laptop screen change across a cashier's leave? (numbers only)"""
import json, subprocess
import numpy as np, cv2
clips = json.load(open("/spike/leaves.json"))
def frame(video, t):
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", f"/videos/{video}",
                          "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_GRAYSCALE) if out else None
def covered(people, t, box):
    frame_people = min(people, key=lambda p: abs(p[0] - t))[1]
    x1, y1, x2, y2 = box; area = (x2 - x1) * (y2 - y1)
    for a, b, c, d in frame_people:
        inter = max(0, min(x2, c) - max(x1, a)) * max(0, min(y2, d) - max(y1, b))
        if inter / area > 0.3: return True
    return False
def crop(img, box):
    h, w = img.shape; x1, y1, x2, y2 = box
    return cv2.resize(img[int(y1*h):int(y2*h), int(x1*w):int(x2*w)], (64, 40)).astype(np.float32)
for c in clips:
    if not c["laptop"] or not c["leaves"]: continue
    for t in c["leaves"]:
        def window(a, b):
            ts = [x for x in np.arange(t + a, t + b + 1e-6, 0.5) if 0 <= x < c["duration"]]
            frames = [frame(c["video"], x) for x in ts if not covered(c["people"], x, c["laptop"])]
            return [crop(f, c["laptop"]) for f in frames if f is not None]
        before, after = window(-4, -1), window(1.5, 4)
        row = {"clip": c["clip"], "label": c["label"], "t": t, "n_before": len(before), "n_after": len(after)}
        if before and after:
            b, a = np.median(before, 0), np.median(after, 0)
            a = a * (b.mean() / max(a.mean(), 1))
            row["diff"] = round(float(np.abs(a - b).mean()), 1)
            row["bright_before"], row["bright_after"] = round(float(b.mean()), 1), round(float(a.mean()), 1)
        print(json.dumps(row), flush=True)
