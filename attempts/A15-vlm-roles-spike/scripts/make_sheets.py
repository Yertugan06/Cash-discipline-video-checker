import json, sys
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root = Path(sys.argv[1]); out = root / "sheets"; out.mkdir(exist_ok=True)
rows = defaultdict(list)
for line in (root / "results.jsonl").read_text().splitlines():
    r = json.loads(line); rows[r["clip"]].append(r)
font = ImageFont.load_default(size=15)
for clip, frames in rows.items():
    tiles = []
    for r in frames:
        im = Image.open(root / "img" / r["image"]).convert("RGB")
        d = ImageDraw.Draw(im); w, h = im.size
        people = {p.get("id"): p for p in (r["vlm"] or {}).get("people", [])}
        for i, (x1, y1, x2, y2) in enumerate(r["boxes"], 1):
            p = people.get(i)
            tag = f"{i}:{p['role'][:9]}" if p else f"{i}:MISSING"
            ty = min(h - 18, y2 * h + 2)
            d.rectangle((x1 * w, ty, x1 * w + d.textlength(tag, font=font) + 6, ty + 18), fill=(0, 0, 0))
            d.text((x1 * w + 3, ty + 1), tag, fill=(255, 255, 0), font=font)
        sit = (r["vlm"] or {}).get("situation", "PARSE-FAIL")
        d.rectangle((0, 0, w, 22), fill=(0, 0, 0)); d.text((4, 3), f"t={r['t']}s {sit}", fill=(0, 255, 255), font=font)
        tiles.append(im)
    W = sum(t.width for t in tiles); H = max(t.height for t in tiles)
    sheet = Image.new("RGB", (W, H)); x = 0
    for t in tiles: sheet.paste(t, (x, 0)); x += t.width
    sheet.thumbnail((1600, 800)); sheet.save(out / (Path(clip).stem.replace("Х", "X") + ".jpg"), quality=85)
print(sorted(p.name for p in out.iterdir()))
