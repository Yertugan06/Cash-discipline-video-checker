"""Люди по детектору D-FINE-S (Apache-2.0, обучен на COCO): ~8 мс на кадр на RTX 4050 против ~3 с анкеты VLM.

4B плохо считает людей (клиента принимает за второго человека у кассира, путает людей за стеклом), детектор — стабильно.
Из рамок по секундам:
  n — людей в комнате: ноги (низ рамки) не выше линии пола у стола/двери — люди за стеклом стоят дальше и выше в кадре;
  s — из них стоят: рамка вытянута по вертикали (высота/ширина в пикселях ≥ 2,1).
Правила (пороги подобраны на 40 видео: на 19 чистых — ни одного срабатывания):
  two_clients — в комнате ≥ 3 человек дольше 5 с и это не инкассатор;
  outsider    — стоят ≥ 2 человек дольше 2 с (клиент садится к столу, посторонний стоит рядом с кассиром).
Если torch/transformers не установлены, модуль выключается, и конвейер работает по-старому (подтверждение через VLM).
"""
import os
from statistics import median

try:
    import torch
    from transformers import AutoImageProcessor, DFineForObjectDetection
    AVAILABLE = True
except Exception:                                   # noqa: BLE001
    AVAILABLE = False

from PIL import Image

MODEL_ID = os.environ.get('DET_MODEL', 'ustc-community/dfine-small-coco')
P = {'thr': 0.45, 'stand_ar': 2.1, 'crowd': 3, 'crowd_s': 5, 'stand': 2, 'stand_s': 2}
_M = {}


def _load():
    if not _M:
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        proc = AutoImageProcessor.from_pretrained(MODEL_ID)
        model = DFineForObjectDetection.from_pretrained(MODEL_ID).to(dev).eval()
        if dev == 'cuda': model = model.half()
        _M.update(proc=proc, model=model, dev=dev)
    return _M['proc'], _M['model'], _M['dev']


def detect_frames(frames, batch=8):
    """{t: [[x1,y1,x2,y2,score], ...]} — рамки людей в долях кадра."""
    proc, model, dev = _load()
    out = {}
    for i in range(0, len(frames), batch):
        chunk = frames[i:i + batch]
        ims = [Image.open(f['path']).convert('RGB') for f in chunk]
        inp = proc(images=ims, return_tensors='pt').to(dev)
        if dev == 'cuda': inp['pixel_values'] = inp['pixel_values'].half()
        with torch.no_grad(): res = model(**inp)
        res = proc.post_process_object_detection(res, threshold=P['thr'], target_sizes=[(im.height, im.width) for im in ims])
        for f, im, r in zip(chunk, ims, res):
            W, H = im.size
            out[f['t']] = [[b[0] / W, b[1] / H, b[2] / W, b[3] / H, s] for s, l, b in
                           zip(r['scores'].tolist(), r['labels'].tolist(), r['boxes'].tolist()) if model.config.id2label[l] == 'person']
    return out


def in_room(p, boxes):
    desk, door = boxes.get('desk'), boxes.get('door')
    floor = (min(desk[1] if desk else 1000, door[3] if door else 1000) / 1000 - 0.04) if (desk or door) else 0.45
    return p[3] >= floor or (p[3] - p[1]) >= 0.30


def standing(p, aspect):
    """aspect = ширина кадра / высота кадра (в пикселях)."""
    return (p[3] - p[1]) / max(1e-6, p[2] - p[0]) / aspect >= P['stand_ar']


def per_second(det, boxes, aspect, duration):
    n, s = [], []
    for sec in range(int(duration) + 1):
        ins = [[q for q in ps if in_room(q, boxes)] for t, ps in det.items() if sec <= t < sec + 1]
        n.append(round(median(len(x) for x in ins)) if ins else 0)
        s.append(round(median(sum(standing(q, aspect) for q in x) for x in ins)) if ins else 0)
    return n, s


def _runs(xs, pred, min_len):
    out, i = [], 0
    while i < len(xs):
        if pred(xs[i]):
            j = i
            while j + 1 < len(xs) and pred(xs[j + 1]): j += 1
            if j - i + 1 >= min_len: out.append((i, j))
            i = j + 1
        else: i += 1
    return out


def events(n, s, collector_at):
    """Нарушения по людям: [{'rule', 't', 'i', 'extra'}] в формате timeline_rules.detect."""
    ev = []
    for i, j in _runs(n, lambda v: v >= P['crowd'], P['crowd_s']):
        if sum(collector_at(k) for k in range(i, j + 1)) <= (j - i + 1) / 2:
            ev.append({'rule': 'two_clients', 't': float(i), 'i': None, 'extra': f'{max(n[i:j + 1])} чел. в комнате {j - i + 1} с'})
    for i, j in _runs(s, lambda v: v >= P['stand'], P['stand_s']):
        ev.append({'rule': 'outsider', 't': float(i), 'i': None, 'extra': f'стоят {max(s[i:j + 1])} чел. {j - i + 1} с'})
    return ev
