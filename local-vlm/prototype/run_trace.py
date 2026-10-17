"""Трасса обработки одного видео: что делал конвейер, сколько это заняло, что ответила модель и на каких кадрах.

Папка трассы:
  index.html          — просмотрщик (открывается и с диска, и через сервер; во время обработки обновляется сам)
  trace.js            — данные (window.TRACE = {...}), переписывается после каждого шага
  boxes.jpg           — опорный кадр с найденными рамками стола / сейфа / ноутбука / двери
  timeline.png        — матрица состояний: строки — поля анкеты, столбцы — отсчёты времени, красные линии — нарушения
  frames/*.jpg        — кадры, отправленные в анкету
  zoom/*.jpg          — увеличенные кропы с ответом модели
  confirm/*.jpg       — кадры подтверждения кандидатов
  evidence/*.jpg      — кадры-доказательства с рамкой объекта и подписью
В трассе есть кадры видео, поэтому она хранится только локально (переменная TRACE=0 выключает запись).
"""
import json, os, shutil, threading, time

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BOX_COLORS = {'desk': (46, 160, 67), 'safe': (230, 126, 34), 'laptop': (52, 120, 246), 'door': (142, 68, 173)}
BOX_NAMES = {'desk': 'стол', 'safe': 'сейф', 'laptop': 'ноутбук', 'door': 'дверь'}
RULE_BOX = {'leave_cash': 'desk', 'dirty_desk': 'desk', 'merge_cash': 'desk', 'leave_docs': 'desk', 'personal_items': 'desk',
            'food': 'desk', 'no_id': 'desk', 'collector_quick': 'desk', 'leave_key': 'safe', 'safe_open': 'safe',
            'bag_to_safe_no_count': 'safe', 'leave_laptop': 'laptop', 'door_open': 'door'}
TIMELINE_FIELDS = [
    ('cashier_at_desk', 'кассир за столом'), ('cashier_in_room', 'кассир в комнате'), ('people_cashier_side', 'людей у кассира'),
    ('clients_at_desk', 'клиентов у стола'), ('person_at_door', 'человек в двери'), ('collector_present', 'инкассатор'),
    ('desk_cash', 'деньги на столе'), ('desk_bag', 'сумка на столе'), ('desk_documents', 'документы на столе'),
    ('desk_personal_items', 'личные вещи'), ('desk_food_drink', 'еда / напитки'), ('phone_in_cashier_hand', 'телефон в руке'),
    ('id_document_visible', 'удостоверение'), ('counting_machine_in_use', 'счётная машина'), ('cash_in_hands_of', 'деньги в руках'),
    ('safe_door', 'сейф'), ('laptop_screen', 'экран'), ('room_door', 'дверь')]
ENUM_COLORS = {'open': (231, 76, 60), 'closed': (189, 195, 199), 'not_visible': (240, 240, 240), 'unlocked': (231, 76, 60),
               'lock_screen': (46, 160, 67), 'off_or_closed': (120, 120, 120), 'nobody': (240, 240, 240), 'cashier': (52, 120, 246),
               'client': (230, 126, 34), 'collector': (142, 68, 173), 'several': (192, 57, 43)}


def font(size):
    for f in ('arial.ttf', 'DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(draw, xy, text, fill, size=14):
    f = font(size); x, y = xy
    l, t, r, b = draw.textbbox((x, y), text, font=f)
    draw.rectangle((l - 3, t - 2, r + 3, b + 2), fill=fill)
    draw.text((x, y), text, fill=(255, 255, 255), font=f)


def to_px(box, w, h):
    return [box[0] * w / 1000, box[1] * h / 1000, box[2] * w / 1000, box[3] * h / 1000]


def draw_persons(im, persons, color=(46, 204, 113), room=None):
    """Рамки людей детектора (доли кадра). room(p) → False: человек за стеклом — серая тонкая рамка, в подсчёт не идёт."""
    d = ImageDraw.Draw(im); w, h = im.size
    for n, p in enumerate(persons or [], 1):
        x1, y1, x2, y2 = p[0] * w, p[1] * h, p[2] * w, p[3] * h
        if room is not None and not room(p):
            d.rectangle((x1, y1, x2, y2), outline=(150, 150, 150), width=1); label(d, (x1 + 2, y1 + 2), 'за стеклом', (120, 120, 120), 10)
            continue
        d.rectangle((x1, y1, x2, y2), outline=color, width=3)
        label(d, (x1 + 3, y1 + 3), f'{n} · {p[4]:.2f}', color, 12)


class Tracer:
    """Пустышка, если dir=None: все методы ничего не делают."""

    def __init__(self, out_dir, video_name=''):
        self.dir = out_dir; self.on = bool(out_dir); self.lock = threading.Lock()
        self.data = {'video': video_name, 'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'status': 'processing', 'stage': '',
                     'steps': [], 'frames': [], 'boxes': {}, 'zoom': [], 'confirm': [], 'actions': [], 'rules': [], 'dropped': [], 'result': None,
                     'images': {}}
        self.t0 = time.time(); self._cur = None; self.room = None     # room(p) — человек в комнате (для рамок)
        if self.on:
            for sub in ('frames', 'zoom', 'confirm', 'evidence', 'actions'): os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
            shutil.copy(os.path.join(HERE, 'static', 'trace.html'), os.path.join(out_dir, 'index.html'))
            self.flush()

    # ---------- шаги ----------
    def step(self, name, **info):
        """Закрывает предыдущий шаг и открывает новый."""
        if not self.on: return
        now = time.time()
        with self.lock:
            if self._cur: self._cur['dur_s'] = round(now - self._cur['_t'], 2); self._cur.pop('_t', None)
            self._cur = {'name': name, 'start_s': round(now - self.t0, 2), '_t': now, **info} if name else None
            if self._cur: self.data['steps'].append(self._cur)
            self.data['stage'] = name or ''
        self.flush()

    def note(self, **info):
        if self.on and self._cur: self._cur.update(info)

    # ---------- данные ----------
    def frames(self, picked, jobs, reuse_of, results, frame_paths, det=None):
        if not self.on: return
        sent = {f['t'] for f in jobs}
        for f in picked:
            r = results.get(f['t']) or results.get(reuse_of.get(f['t']), {})
            item = {'t': f['t'], 'sent': f['t'] in sent, 'reused_from': reuse_of.get(f['t']), 'latency_s': r.get('latency_s'),
                    'ok': r.get('ok'), 'state': r.get('state')}
            if f['t'] in sent:
                im = Image.open(frame_paths[f['t']]).convert('RGB')
                if det: draw_persons(im, det.get(f['t']), room=self.room)
                im.thumbnail((180, 320))
                rel = f"frames/{f['t']:07.2f}.jpg"; im.save(os.path.join(self.dir, rel), quality=80); item['img'] = rel
            self.data['frames'].append(item)
        self.flush()

    def boxes(self, frame_path, boxes, persons=None):
        if not self.on: return
        self.data['boxes'] = boxes
        im = Image.open(frame_path).convert('RGB'); draw_persons(im, persons, room=self.room); d = ImageDraw.Draw(im); w, h = im.size
        for k, b in boxes.items():
            if not b: continue
            x1, y1, x2, y2 = to_px(b, w, h); c = BOX_COLORS.get(k, (255, 0, 0))
            d.rectangle((x1, y1, x2, y2), outline=c, width=3); label(d, (x1 + 4, max(0, y1 - 20)), BOX_NAMES.get(k, k), c)
        im.save(os.path.join(self.dir, 'boxes.jpg'), quality=85); self.data['images']['boxes'] = 'boxes.jpg'
        self.flush()

    def zoom(self, kind, t, answer, frame_path, box, margin, changed=None):
        if not self.on: return
        item = {'kind': kind, 't': t, 'answer': answer, 'changed': changed or []}
        if box:
            im = Image.open(frame_path).convert('RGB'); w, h = im.size
            x1, y1, x2, y2 = [v / 1000 for v in box]; bw, bh = x2 - x1, y2 - y1
            c = im.crop((int(max(0, x1 - margin * bw) * w), int(max(0, y1 - margin * bh) * h),
                         int(min(1, x2 + margin * bw) * w), int(min(1, y2 + margin * bh) * h)))
            c.thumbnail((320, 320)); d = ImageDraw.Draw(c)
            txt = ', '.join(f'{k}={v}' for k, v in (answer or {}).items()) if isinstance(answer, dict) else str(answer)
            label(d, (4, 4), f'{t:.1f} с', BOX_COLORS.get(kind, (80, 80, 80)), 12)
            label(d, (4, c.height - 20), txt[:48], (40, 40, 40), 12)
            rel = f'zoom/{kind}_{t:07.2f}.jpg'; c.save(os.path.join(self.dir, rel), quality=82); item['img'] = rel
        with self.lock: self.data['zoom'].append(item)

    def confirm(self, rule, t, answers, frame_paths, ok):
        if not self.on: return
        imgs = []
        for (tt, a), p in zip(answers, frame_paths):
            im = Image.open(p).convert('RGB'); im.thumbnail((200, 360)); d = ImageDraw.Draw(im)
            label(d, (4, 4), f'{tt:.1f} с', (60, 60, 60), 12)
            label(d, (4, im.height - 20), f'стоят {a.get("people_standing")} / сидят {a.get("people_sitting")}', (40, 40, 40), 12)
            rel = f'confirm/{rule}_{t:06.1f}_{tt:06.1f}.jpg'; im.save(os.path.join(self.dir, rel), quality=82); imgs.append(rel)
        self.data['confirm'].append({'rule': rule, 't': t, 'ok': ok, 'answers': [a for _, a in answers], 'imgs': imgs})
        self.flush()

    def action(self, t0, why, answer, frame_paths, latency):
        """Окно действий: лента из 4 кадров с ответом модели."""
        if not self.on: return
        ims = []
        for k, p in enumerate(frame_paths):
            im = Image.open(p).convert('RGB'); im.thumbnail((160, 300)); d = ImageDraw.Draw(im)
            label(d, (3, 3), f'{t0 + k:.0f} с', (60, 60, 60), 11); ims.append(im)
        strip = Image.new('RGB', (sum(i.width for i in ims) + 3 * (len(ims) - 1), ims[0].height), (255, 255, 255)); x = 0
        for im in ims: strip.paste(im, (x, 0)); x += im.width + 3
        rel = f'actions/{why}_{t0:06.1f}.jpg'; strip.save(os.path.join(self.dir, rel), quality=82)
        with self.lock: self.data['actions'].append({'t0': t0, 'why': why, 'answer': answer, 'latency_s': round(latency, 1), 'img': rel})
        self.flush()

    def evidence(self, idx, rule, title, t, frame_path, boxes, persons=None):
        """Кадр-доказательство с рамкой связанного объекта (или людей) и подписью; возвращает путь к картинке."""
        if not self.on: return None
        im = Image.open(frame_path).convert('RGB')
        if persons: draw_persons(im, persons, (231, 76, 60), room=self.room)
        d = ImageDraw.Draw(im); w, h = im.size
        k = RULE_BOX.get(rule)
        if k and boxes.get(k):
            x1, y1, x2, y2 = to_px(boxes[k], w, h); d.rectangle((x1, y1, x2, y2), outline=(231, 76, 60), width=4)
        label(d, (6, 6), f'{t:.1f} с', (231, 76, 60), 16)
        label(d, (6, h - 26), title[:60], (150, 30, 30), 13)
        rel = f'evidence/{idx}_{t:06.1f}.jpg'; im.save(os.path.join(self.dir, rel), quality=85)
        return rel

    def timeline(self, samples, violations, zoom_changes, people=None):
        """Матрица состояний: строки — поля, столбцы — отсчёты; точка — значение поменяла увеличенная проверка.
        people = (n, s) по секундам от детектора — две нижние строки."""
        if not self.on or not samples: return
        fields = list(TIMELINE_FIELDS)
        if people:
            n, s = people
            samples = [{'t': x['t'], 'state': {**x['state'], '_n': n[min(len(n) - 1, int(x['t']))] if n else 0,
                                               '_s': s[min(len(s) - 1, int(x['t']))] if s else 0}} for x in samples]
            fields += [('_n', 'людей (детектор)'), ('_s', 'стоят (детектор)')]
        cw, ch, lw, top = 12, 16, 150, 34
        W = lw + cw * len(samples) + 10; H = top + ch * len(fields) + 26
        im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im); f = font(11)
        for r, (k, name) in enumerate(fields):
            y = top + r * ch; d.text((4, y + 2), name, fill=(40, 40, 40), font=f)
            for c, s in enumerate(samples):
                v = s['state'].get(k); x = lw + c * cw
                if isinstance(v, bool): col = (52, 120, 246) if v else (240, 240, 240)
                elif isinstance(v, int): col = [(240, 240, 240), (149, 196, 255), (52, 120, 246), (20, 60, 160)][min(v, 3)]
                else: col = ENUM_COLORS.get(v, (210, 210, 210))
                d.rectangle((x, y, x + cw - 2, y + ch - 2), fill=col)
                if (s['t'], k) in zoom_changes: d.ellipse((x + 3, y + 4, x + 7, y + 8), fill=(0, 0, 0))
        for c, s in enumerate(samples):
            if c % max(1, round(10 / max(1e-6, (samples[-1]['t'] - samples[0]['t']) / max(1, len(samples) - 1)))) == 0:
                d.text((lw + c * cw, H - 20), f"{s['t']:.0f}", fill=(90, 90, 90), font=f)
        span = max(1e-6, samples[-1]['t'] - samples[0]['t'])
        for v in violations:
            x = lw + (v['t'] - samples[0]['t']) / span * cw * (len(samples) - 1) + cw / 2
            d.line((x, top - 4, x, H - 24), fill=(231, 76, 60), width=2); d.text((x + 3, 4 + 12 * (violations.index(v) % 2)), v['rule'], fill=(200, 40, 40), font=f)
        im.save(os.path.join(self.dir, 'timeline.png')); self.data['images']['timeline'] = 'timeline.png'
        self.flush()

    def finish(self, result=None, debug=None, rules=None, dropped=None, error=None):
        if not self.on: return
        self.step(None)
        self.data.update(status='failed' if error else 'done', error=error, total_s=round(time.time() - self.t0, 1),
                         rules=rules or self.data['rules'], dropped=dropped or self.data['dropped'])
        if result is not None:
            self.data['result'] = {'verdict': result['verdict'],
                                   'violations': [{k: v[k] for k in ('type', 'timecode_sec', 'description')} | {'norm': v.get('norm'), 'evidence': v.get('_evidence_imgs', [])}
                                                  for v in result['violations']]}
        if debug: self.data['debug'] = {k: v for k, v in debug.items() if k != 'rules'}
        self.flush()

    def flush(self):
        if not self.on: return
        with self.lock:
            self.data['elapsed_s'] = round(time.time() - self.t0, 1)
            txt = 'window.TRACE = ' + json.dumps(self.data, ensure_ascii=False, default=str) + ';\n'
        tmp = os.path.join(self.dir, 'trace.js.tmp')
        with open(tmp, 'w', encoding='utf-8') as f: f.write(txt)
        os.replace(tmp, os.path.join(self.dir, 'trace.js'))
