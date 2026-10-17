"""Эксперимент: детектор D-FINE (Apache-2.0, COCO) на всех кадрах видео — люди и предметы COCO.

  prototype/.venv_det/Scripts/python prototype/tools/people_dfine.py --videos open/open/videos --out prototype/work/runs/dfine [--only X-18,X-30]

На выходе для каждого видео:
  <vid>.jsonl   — по кадру (2 fps): t, persons [[x1,y1,x2,y2,score] в долях 0..1], objects [{label, box, score}]
  <vid>.jpg     — лист кадров (каждая 2-я секунда) с нарисованными рамками: люди — зелёные с номером, предметы — оранжевые
  _summary.json — время детектора на кадр, сколько людей максимум и т. п.
"""
import argparse, glob, json, os, subprocess, sys, tempfile, time

import torch
from PIL import Image, ImageDraw, ImageFont
from transformers import AutoImageProcessor, DFineForObjectDetection

KEEP = {'person', 'cell phone', 'cup', 'bottle', 'handbag', 'backpack', 'laptop', 'book', 'suitcase', 'chair', 'wine glass', 'sandwich',
        'banana', 'apple', 'donut', 'cake', 'keyboard', 'mouse', 'remote', 'tv'}
MODELS = ['ustc-community/dfine-small-coco', 'ustc-community/dfine_s_coco', 'ustc-community/dfine-medium-coco']


def load_model(name, device):
    for n in ([name] if name else MODELS):
        try:
            proc = AutoImageProcessor.from_pretrained(n); model = DFineForObjectDetection.from_pretrained(n).to(device).eval()
            if device == 'cuda': model = model.half()
            return n, proc, model
        except Exception as e:                      # noqa: BLE001
            print('cannot load', n, type(e).__name__, str(e)[:120])
    raise SystemExit('no D-FINE checkpoint could be loaded')


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', required=True); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    ap.add_argument('--model', default=''); ap.add_argument('--thr', type=float, default=0.45); ap.add_argument('--fps', type=float, default=2.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    name, proc, model = load_model(a.model, device)
    print('model', name, 'device', device, flush=True)
    files = {os.path.splitext(os.path.basename(f))[0].replace('Х', 'X'): f for f in glob.glob(os.path.join(a.videos, '*'))
             if f.lower().endswith(('.mov', '.mp4', '.mkv', '.avi', '.m4v', '.webm'))}
    only = set(filter(None, a.only.split(',')))
    summary = {'model': name, 'device': device, 'videos': {}}
    for vid in sorted(files, key=lambda v: int(v.split('-')[1])):
        if only and vid not in only: continue
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', files[vid], '-vf', f'fps={a.fps}', '-q:v', '3', os.path.join(tmp, '%06d.jpg')], check=True)
            paths = sorted(glob.glob(os.path.join(tmp, '*.jpg')))
            rows, t_det = [], 0.0
            for i in range(0, len(paths), 8):                         # батч по 8 кадров
                ims = [Image.open(p).convert('RGB') for p in paths[i:i + 8]]
                inp = proc(images=ims, return_tensors='pt').to(device)
                if device == 'cuda': inp['pixel_values'] = inp['pixel_values'].half()
                t0 = time.time()
                with torch.no_grad(): out = model(**inp)
                if device == 'cuda': torch.cuda.synchronize()
                t_det += time.time() - t0
                res = proc.post_process_object_detection(out, threshold=a.thr, target_sizes=[(im.height, im.width) for im in ims])
                for j, (im, r) in enumerate(zip(ims, res)):
                    W, H = im.size; persons, objects = [], []
                    for s, l, b in zip(r['scores'].tolist(), r['labels'].tolist(), r['boxes'].tolist()):
                        lab = model.config.id2label[l]
                        if lab not in KEEP: continue
                        box = [round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)]
                        if lab == 'person': persons.append(box + [round(s, 3)])
                        else: objects.append({'label': lab, 'box': box, 'score': round(s, 3)})
                    rows.append({'t': round((i + j) / a.fps, 2), 'persons': persons, 'objects': objects})
            with open(os.path.join(a.out, f'{vid}.jsonl'), 'w', encoding='utf-8') as f:
                for r in rows: f.write(json.dumps(r) + '\n')
            # лист кадров с рамками: каждая 2-я секунда, до 24 кадров
            step = max(1, round(2 * a.fps)); pick = list(range(0, len(paths), step))[:24]
            tiles = []
            for k in pick:
                im = Image.open(paths[k]).convert('RGB'); W, H = im.size; d = ImageDraw.Draw(im); f = font(16)
                for n, p in enumerate(rows[k]['persons'], 1):
                    x1, y1, x2, y2 = p[0] * W, p[1] * H, p[2] * W, p[3] * H
                    d.rectangle((x1, y1, x2, y2), outline=(46, 204, 113), width=3); d.text((x1 + 3, y1 + 2), f'{n} {p[4]:.2f}', fill=(46, 204, 113), font=f)
                for o in rows[k]['objects']:
                    x1, y1, x2, y2 = o['box'][0] * W, o['box'][1] * H, o['box'][2] * W, o['box'][3] * H
                    d.rectangle((x1, y1, x2, y2), outline=(243, 156, 18), width=2); d.text((x1 + 2, y2 - 16), o['label'], fill=(243, 156, 18), font=font(13))
                d.rectangle((0, 0, 70, 22), fill=(0, 0, 0)); d.text((4, 2), f"{rows[k]['t']:.0f} s", fill=(255, 255, 255), font=f)
                im.thumbnail((232, 424)); tiles.append(im)
            cols = 8; tw, th = tiles[0].size; sheet = Image.new('RGB', (cols * tw, ((len(tiles) + cols - 1) // cols) * th), (255, 255, 255))
            for n, im in enumerate(tiles): sheet.paste(im, ((n % cols) * tw, (n // cols) * th))
            sheet.save(os.path.join(a.out, f'{vid}.jpg'), quality=82)
        mx = max((len(r['persons']) for r in rows), default=0)
        summary['videos'][vid] = {'frames': len(rows), 'det_ms_per_frame': round(1000 * t_det / max(1, len(rows)), 1), 'max_persons': mx}
        print(f"{vid}: {len(rows)} frames, {1000 * t_det / max(1, len(rows)):.1f} ms/frame, max persons {mx}", flush=True)
        json.dump(summary, open(os.path.join(a.out, '_summary.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
