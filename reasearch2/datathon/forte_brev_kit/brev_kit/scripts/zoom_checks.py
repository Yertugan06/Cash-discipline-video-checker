"""Увеличенные проверки мелких объектов: ключ в замке сейфа, дверца сейфа, экран ноутбука, дверь кабины.
1) VLM один раз находит рамки объектов на кадре (координаты 0–1000), 2) кадр обрезается по рамке и увеличивается,
3) VLM отвечает на узкий вопрос по кропу. Ответы перезаписывают поля анкеты → правила работают по уточнённым состояниям.

Золотые кадры (оценка точности):
  python scripts/zoom_checks.py --gold-frames work/gold_frames/gold_frames.json --states runs/X_gold/states --out runs/X_gold/states_zoom ...
  python scripts/eval_states.py --pred runs/X_gold/states_zoom --gold data/gold_states.csv
Целые видео (проверки только в моменты, когда кассир ушёл / вошёл):
  python scripts/zoom_checks.py --frames work/frames --states runs/X/states --out runs/X/states_zoom ...
  python scripts/timeline_rules.py --states runs/X/states_zoom --out runs/X/violations_zoom
"""
import argparse, glob, json, os, statistics, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import chat, load_prompt
from PIL import Image

BOX = {'type': 'array', 'items': {'type': 'integer', 'minimum': 0, 'maximum': 1000}, 'minItems': 4, 'maxItems': 4}
LOCATE_SCHEMA = {'type': 'object', 'additionalProperties': False,
                 'required': ['safe_found', 'safe_box', 'laptop_found', 'laptop_box', 'door_found', 'door_box'],
                 'properties': {'safe_found': {'type': 'boolean'}, 'safe_box': BOX, 'laptop_found': {'type': 'boolean'},
                                'laptop_box': BOX, 'door_found': {'type': 'boolean'}, 'door_box': BOX}}
LOCATE_Q = ('Find these objects in the image and give their bounding boxes as [x1, y1, x2, y2] in RELATIVE coordinates from 0 to 1000 '
            '(0,0 = top-left corner of the image, 1000,1000 = bottom-right):\n'
            '- safe: the grey metal safe/cabinet (its front door with the lock);\n- laptop: the laptop screen;\n'
            '- door: the glass door of the room (the door leaf and its frame).\n'
            'If an object is not visible set *_found=false and its box to [0,0,0,0].')
CHECKS = {
    'safe': ({'type': 'object', 'additionalProperties': False, 'required': ['safe_door', 'key_in_lock'],
              'properties': {'safe_door': {'type': 'string', 'enum': ['open', 'closed', 'unclear']},
                             'key_in_lock': {'type': 'string', 'enum': ['yes', 'no', 'unclear']}}},
             'This is a zoomed crop of a metal safe/cabinet. 1) Is the safe door open or closed? '
             '2) Look at the lock/keyhole on the front of the door: is a key sticking out of it (often a key on a ring with a small keychain hanging down)? '
             'Answer yes only if you actually see a key in the lock.'),
    'laptop': ({'type': 'object', 'additionalProperties': False, 'required': ['screen'],
                'properties': {'screen': {'type': 'string', 'enum': ['unlocked', 'lock_screen', 'off_or_closed', 'unclear']}}},
               'This is a zoomed crop of a laptop. What does the screen show? unlocked = an application window (spreadsheet/table with rows, '
               'document, browser, bright white window); lock_screen = a full-screen photo/landscape picture, maybe with a clock, and NO windows '
               '(Windows lock screen); off_or_closed = dark screen or closed lid.'),
    'door': ({'type': 'object', 'additionalProperties': False, 'required': ['door'],
              'properties': {'door': {'type': 'string', 'enum': ['open', 'closed', 'unclear']}}},
             'This is a zoomed crop of a glass room door. Is the door open (the leaf is swung away from the frame, a gap or opening is visible, '
             'or someone is passing through) or closed (the leaf is flush with its frame)?'),
}
APPLY = {'safe': {'safe_door': 'safe_door', 'key_in_lock': 'key_in_safe_lock'}, 'laptop': {'screen': 'laptop_screen'}, 'door': {'door': 'room_door'}}


def crop(path, box, margin=0.25, out_side=896):
    im = Image.open(path).convert('RGB'); W, H = im.size
    x1, y1, x2, y2 = [v / 1000 for v in box]
    if x2 <= x1 or y2 <= y1: return None
    w, h = x2 - x1, y2 - y1
    x1, y1, x2, y2 = max(0, x1 - margin * w), max(0, y1 - margin * h), min(1, x2 + margin * w), min(1, y2 + margin * h)
    c = im.crop((int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)))
    k = out_side / max(c.size); c = c.resize((max(1, round(c.width * k)), max(1, round(c.height * k))), Image.LANCZOS)
    f = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False); c.save(f.name, quality=92); return f.name


def locate(paths, a, system):
    """Рамки объектов: медиана по нескольким кадрам (на одном объект может закрывать человек)."""
    boxes = {'safe': [], 'laptop': [], 'door': []}
    for p in paths:
        ans, raw, lat, err = chat(a.base_url, a.model, system, LOCATE_Q, [p], LOCATE_SCHEMA, a.structured, a.locate_side)
        for k in boxes:
            if ans and ans.get(f'{k}_found') and len(ans.get(f'{k}_box', [])) == 4:
                boxes[k].append(ans[f'{k}_box'])
    return {k: [int(statistics.median(b[i] for b in v)) for i in range(4)] if v else None for k, v in boxes.items()}


def check(path, boxes, kinds, a, system):
    res = {}
    for k in kinds:
        if not boxes.get(k): continue
        cp = crop(path, boxes[k])
        if not cp: continue
        schema, q = CHECKS[k]
        ans, raw, lat, err = chat(a.base_url, a.model, system, q, [cp], schema, a.structured, a.max_side)
        os.unlink(cp)
        if ans:
            for src, dst in APPLY[k].items():
                if ans.get(src) not in (None, 'unclear'): res[dst] = ans[src]
    return res


def times_to_check(rows):
    """Моменты для проверки в целом видео: кассир не за столом (ключ, сейф, экран) и после входа кого-то в дверь (дверь)."""
    S = [r for r in rows if r.get('ok')]
    away = [r['t'] for r in S if not r['state']['cashier_at_desk']]
    after_entry = []
    for i in range(1, len(S)):
        s0, s1 = S[i - 1]['state'], S[i]['state']
        if (not s0['cashier_at_desk'] and s1['cashier_at_desk']) or s1['person_at_door']:
            after_entry += [S[i]['t'] + d for d in (2, 5, 8)]
    pick = lambda ts, step: sorted({round(t / step) * step for t in ts})
    return {'safe': pick(away, 3), 'laptop': pick(away, 3), 'door': pick(after_entry, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--states', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--frames'); ap.add_argument('--gold-frames')
    ap.add_argument('--model', required=True); ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    ap.add_argument('--structured', default='json_schema'); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--max-side', type=int, default=896); ap.add_argument('--locate-side', type=int, default=1024)
    a = ap.parse_args()
    system = load_prompt('system.txt'); os.makedirs(a.out, exist_ok=True); log = []

    def process(vid):
        rows = [json.loads(l) for l in open(os.path.join(a.states, f'{vid}.jsonl'), encoding='utf-8')]
        if a.gold_frames:
            frames = [f for f in json.load(open(a.gold_frames, encoding='utf-8'))['frames'] if f['video'] == vid]
            plan = {f['t']: ['safe', 'laptop', 'door'] for f in frames}
            ref = [frames[0]['path']]
        else:
            frames = json.load(open(os.path.join(a.frames, vid, 'frames.json'), encoding='utf-8'))['frames']
            tt = times_to_check(rows); plan = {}
            for k, ts in tt.items():
                for t in ts: plan.setdefault(t, []).append(k)
            n = len(frames); ref = [frames[i]['path'] for i in sorted({0, n // 2, n - 1})]
        if not plan:
            boxes, upd = None, {}
        else:
            boxes = locate(ref, a, system); upd = {}
            for t, kinds in sorted(plan.items()):
                fr = min(frames, key=lambda f: abs(f['t'] - t))
                upd[fr['t']] = check(fr['path'], boxes, kinds, a, system)
        n_changed = 0
        with open(os.path.join(a.out, f'{vid}.jsonl'), 'w', encoding='utf-8') as f:
            for r in rows:
                if r.get('ok'):
                    near = [v for t, v in upd.items() if abs(t - r['t']) <= 1.01]
                    for u in near:
                        for k, v in u.items():
                            if r['state'].get(k) != v: r['state'][k] = v; n_changed += 1
                    if near: r['zoom'] = near[0]
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        return {'video': vid, 'boxes': boxes, 'checks': len(upd), 'changed_fields': n_changed}

    vids = [os.path.basename(p)[:-6] for p in sorted(glob.glob(os.path.join(a.states, '*.jsonl')))]
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(process, vids):
            log.append(r); print(f"{r['video']}: checks={r['checks']} changed={r['changed_fields']} boxes={r['boxes']}")
    json.dump(log, open(os.path.join(a.out, '_zoom_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
