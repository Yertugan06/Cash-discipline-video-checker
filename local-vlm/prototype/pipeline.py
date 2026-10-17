"""Конвейер анализа одного видео: кадры → анкета состояний (локальная VLM через Ollama) → увеличенные проверки →
правила → нормы из кодекса → JSON по ТЗ.

Два вида запросов к модели:
  1. Анкета состояния кадра (17 полей, JSON-схема) — кто где находится и что лежит на столе. Это самый дорогой запрос
     (~3,5 с на RTX 4050), поэтому: шаг STEP с, неизменившиеся кадры не отправляются (состояние копируется),
     текст анкеты — в системном промпте (Ollama кэширует префикс), поля, которые 4B по одному кадру не различает, убраны.
  2. Увеличенные проверки (~1 с): кадр обрезается по рамке объекта (стол, сейф, ноутбук, дверь) и модель отвечает на
     узкий вопрос. Только в нужные моменты: стол — когда кассир выходит и когда подходит новый клиент, экран — когда кассира
     нет, дверь — после входа кассира, удостоверение — в сессиях с клиентом, сейф — по сетке. Мелкие объекты так видны лучше.
  3. Подтверждение кандидата «посторонний»: сколько людей стоит/сидит на 4 кадрах — клиент садится, посторонний стоит.
"""
import base64, io, json, os, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, 'brev_kit')
sys.path.insert(0, os.path.join(KIT, 'scripts'))
from common import chat, load_schema, load_prompt, load_codex, validate_state   # noqa: E402
from timeline_rules import detect, to_output                                     # noqa: E402
import zoom_checks as Z                                                          # noqa: E402
from run_trace import Tracer                                                      # noqa: E402
import people                                                                    # noqa: E402
import actions                                                                   # noqa: E402

CFG = {
    'base_url': os.environ.get('VLM_BASE_URL', 'http://127.0.0.1:11434'),
    'model': os.environ.get('VLM_MODEL', 'qwen3-vl:4b-instruct'),
    'structured': os.environ.get('VLM_STRUCTURED', 'ollama'),     # ollama | json_schema (vLLM)
    'prompts': os.path.join(KIT, 'prompts_fast'),
    'step': float(os.environ.get('STEP', '1.5')),                 # базовый шаг между кадрами, с
    'max_calls': int(os.environ.get('MAX_CALLS', '70')),          # бюджет анкет на видео
    'max_gap': float(os.environ.get('MAX_GAP', '6')),             # не реже одной анкеты за N с
    'diff_thr': float(os.environ.get('DIFF_THR', '3.0')),         # порог «кадр не изменился» (средняя разница яркости 0–255)
    'max_side': int(os.environ.get('MAX_SIDE', '1024')),          # 1024 точнее 768 (+7 п.п. на эталонных кадрах)
    'workers': int(os.environ.get('VLM_WORKERS', '2')),
    'zoom': os.environ.get('ZOOM', '1') == '1',                   # увеличенные проверки и подтверждения
    'trace': os.environ.get('TRACE', '1') == '1',                 # писать трассу (кадры с рамками, ответы, время шагов)
    'detector': os.environ.get('DETECTOR', '1') == '1',           # D-FINE для людей (если установлены torch и transformers)
    'action_workers': int(os.environ.get('ACTION_WORKERS', '1')), # параллельных окон 8B (на 6 ГБ — 1, на большой GPU — 4)
    'frame_long_side': 1280,
}
# поля, которые 4B по одному кадру не различает (ключ в замке 0 %, действие кассира почти всегда not_present)
# или которые проверяются увеличенным кропом — в анкете не спрашиваем, ставим нейтральное значение
FAST_DROP = {'key_in_safe_lock': 'not_visible', 'cashier_action': 'other', 'detector_in_use': False,
             'id_document_visible': False, 'other': ''}
FULL_SCHEMA = load_schema()
SCHEMA = {**FULL_SCHEMA, 'required': [k for k in FULL_SCHEMA['required'] if k not in FAST_DROP],
          'properties': {k: v for k, v in FULL_SCHEMA['properties'].items() if k not in FAST_DROP}}
SYSTEM = load_prompt('system.txt', CFG['prompts'])
QUEST = load_prompt('questionnaire.txt', CFG['prompts'])
ZSYSTEM = load_prompt('system.txt', os.path.join(KIT, 'prompts_v2'))             # короткий системный промпт для кропов
CODEX = load_codex()
CFG_Z = type('ZoomCfg', (), {'base_url': CFG['base_url'], 'model': CFG['model'], 'structured': CFG['structured'],
                             'max_side': 896, 'locate_side': 1024})()

ID_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['id_card'],
             'properties': {'id_card': {'type': 'string', 'enum': ['yes', 'no', 'unclear']}}}
ID_Q = ('This is a zoomed crop of a bank cashier desk with a client sitting across. Is an identity document visible - a small plastic ID card '
        '(credit-card size, usually white or light) or a passport booklet - in someone\'s hand, being passed, or lying on the desk? '
        'Banknotes are not ID documents.')
PEOPLE_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['people_standing', 'people_sitting'],
                 'properties': {'people_standing': {'type': 'integer', 'minimum': 0, 'maximum': 5},
                                'people_sitting': {'type': 'integer', 'minimum': 0, 'maximum': 5}}}
PEOPLE_Q = ('Count the people inside this room (ignore people seen through the glass walls outside the room). '
            'people_standing = how many are standing or walking; people_sitting = how many are sitting on chairs.')


def probe_duration(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def extract_frames(path, out_dir, fps=2.0, long_side=1280):
    """Нормализация любого видео (кодек, поворот, разрешение) и кадры с шагом 1/fps. Время кадра = индекс/fps.
    Разрешение не увеличивается, длинная сторона ограничена long_side (мелкие объекты — пачка денег, ключ — не теряются)."""
    os.makedirs(out_dir, exist_ok=True)
    vf = f"fps={fps},scale='min({long_side},iw)':'min({long_side},ih)':force_original_aspect_ratio=decrease"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', vf, '-q:v', '3',
                    os.path.join(out_dir, '%06d.jpg')], check=True)
    files = sorted(f for f in os.listdir(out_dir) if f.endswith('.jpg'))
    return [{'t': round(i / fps, 3), 'path': os.path.join(out_dir, f)} for i, f in enumerate(files)]


def thumb(path):
    im = Image.open(path).convert('L').resize((48, 80))
    return np.asarray(im, dtype=np.float32)


def plan_frames(frames, duration):
    """Выбор кадров для анкеты: шаг STEP, увеличенный для длинных видео до бюджета max_calls."""
    step = max(CFG['step'], duration / CFG['max_calls']) if duration else CFG['step']
    picked, last = [], -1e9
    for f in frames:
        if f['t'] - last >= step - 1e-6:
            picked.append(f); last = f['t']
    return picked, step


def ask(frame):
    q = QUEST.replace('{t}', f"{frame['t']:.1f}")
    st, raw, lat, err = chat(CFG['base_url'], CFG['model'], SYSTEM, q, [frame['path']], SCHEMA, CFG['structured'], CFG['max_side'])
    errs = validate_state(st, SCHEMA) if isinstance(st, dict) else [err or 'no answer']
    if not errs:
        st = {**{k: st[k] for k in FULL_SCHEMA['properties'] if k in st}, **{k: v for k, v in FAST_DROP.items() if k not in st}}
    return {'t': frame['t'], 'state': st if not errs else None, 'ok': not errs, 'latency_s': round(lat, 2), 'errors': errs}


def b64_jpeg(path, max_side=960):
    im = Image.open(path).convert('RGB')
    if max(im.size) > max_side:
        k = max_side / max(im.size); im = im.resize((round(im.width * k), round(im.height * k)))
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------- увеличенные проверки ----------------
def desk_moments(S):
    """Стол: кассир выходит из комнаты (деньги без присмотра) и подходит новый клиент (деньги прошлого клиента)."""
    pick = set()
    for k in range(1, len(S)):
        a, b = S[k - 1]['state'], S[k]['state']
        if a['cashier_in_room'] and not b['cashier_in_room']:
            pick |= {s['t'] for s in S if S[k]['t'] - 2.5 <= s['t'] <= S[k]['t'] + 3.5}
    first_client = next((k for k in range(len(S)) if S[k]['state']['clients_at_desk'] >= 1), None)
    for k in range(1, len(S)):
        if S[k]['state']['clients_at_desk'] >= 1 and S[k - 1]['state']['clients_at_desk'] == 0 and first_client is not None and k > first_client:
            pick |= {s['t'] for s in S if S[k]['t'] - 4.0 <= s['t'] <= S[k]['t']}
    return sorted(pick)[:14]


def grid(t_end, step, cap):
    ts = [round(k * step, 2) for k in range(int(t_end // step) + 1)]
    return ts if len(ts) <= cap else [ts[round(i * (len(ts) - 1) / (cap - 1))] for i in range(cap)]


def door_moments(S):
    """Дверь: 3–9 с после того, как кассир вошёл и села за стол (правило door_open смотрит именно это окно)."""
    pick = set()
    for k in range(1, len(S)):
        if S[k]['state']['cashier_at_desk'] and not S[k - 1]['state']['cashier_at_desk'] and \
                any(not s['state']['cashier_in_room'] or s['state']['person_at_door'] for s in S if S[k]['t'] - 6 <= s['t'] < S[k]['t']):
            pick |= {round(S[k]['t'] + d, 2) for d in (3, 6, 9)}
    return sorted(pick)[:12]


def sessions(S):
    """Сессии с клиентом: подряд идущие отсчёты с клиентом у стола (разрывы до 2,5 с склеиваются)."""
    out = []
    for s in S:
        if s['state']['clients_at_desk'] >= 1:
            if out and s['t'] - out[-1][-1] <= 2.5: out[-1].append(s['t'])
            else: out.append([s['t']])
    return out


def apply_answers(samples, answers, field, conv, win):
    """Ответ кропа переносится на ближайшие отсчёты таймлайна (в пределах win секунд).
    Возвращает изменения [(t отсчёта, поле, t проверки)] — для трассы."""
    if not answers: return []
    out = []
    for s in samples:
        t = min(answers, key=lambda x: abs(x - s['t']))
        if abs(t - s['t']) > win: continue
        v = conv(answers[t])
        if v is not None and s['state'].get(field) != v:
            s['state'][field] = v; out.append((s['t'], field, t))
    return out


def zoom_pass(ex, samples, frames, boxes, duration, progress, tr):
    path_at = lambda t: min(frames, key=lambda f: abs(f['t'] - t))['path']
    chk = lambda kind: (lambda t: Z.check(path_at(t), boxes, [kind], CFG_Z, ZSYSTEM))
    plan = {'desk': desk_moments(samples) if boxes.get('desk') else [],
            'safe': grid(duration, 3, 30) if boxes.get('safe') else [],
            'laptop': [s['t'] for s in samples[::2] if not s['state']['cashier_at_desk']][:8] if boxes.get('laptop') else [],
            'door': [t for t in door_moments(samples) if t <= duration] if boxes.get('door') else []}
    n_checks = sum(len(v) for v in plan.values())
    progress(f'Проверки крупным планом ({n_checks})', 0.8)
    tr.note(**{f'{k}_checks': len(v) for k, v in plan.items()})
    res = {k: dict(zip(ts, ex.map(chk(k), ts))) for k, ts in plan.items()}
    changed = apply_answers(samples, {t: a.get('desk_cash') for t, a in res['desk'].items()}, 'desk_cash', lambda v: v, 0.01)
    changed += apply_answers(samples, {t: a.get('desk_bag') for t, a in res['desk'].items()}, 'desk_bag', lambda v: v, 0.01)
    changed += apply_answers(samples, res['safe'], 'safe_door', lambda a: a.get('safe_door'), 1.6)
    changed += apply_answers(samples, res['laptop'], 'laptop_screen', lambda a: a.get('laptop_screen'), 1.6)
    changed += apply_answers(samples, res['door'], 'room_door', lambda a: a.get('room_door'), 1.6)
    for k, ans in res.items():
        for t, a in ans.items():
            tr.zoom(k, t, a, path_at(t), boxes.get(k), Z.MARGIN.get(k, 0.25),
                    sorted({f'{f}@{st}' for st, f, src in changed if src == t and f in Z.APPLY[k].values()}))

    # удостоверение: в каждой сессии до первого «да» (правилу no_id нужно «было ли хоть раз»)
    n_id = 0
    if boxes.get('desk'):
        def ask_id(t):
            cp = Z.crop(path_at(t), boxes['desk'], margin=0.1)
            a, *_ = chat(CFG['base_url'], CFG['model'], ZSYSTEM, ID_Q, [cp], ID_SCHEMA, CFG['structured'], 896); os.unlink(cp)
            return (a or {}).get('id_card')
        for ts in sessions(samples):
            for i in range(0, min(len(ts), 16), CFG['workers']):
                chunk = ts[i:i + CFG['workers']]
                ans = dict(zip(chunk, ex.map(ask_id, chunk))); n_id += len(chunk)
                ch = apply_answers(samples, ans, 'id_document_visible', lambda v: {'yes': True, 'no': False}.get(v), 0.01); changed += ch
                for t, a in ans.items():
                    tr.zoom('id', t, {'id_card': a}, path_at(t), boxes['desk'], 0.1, [f'{f}@{st}' for st, f, src in ch if src == t])
                if 'yes' in ans.values(): break
    tr.note(id_checks=n_id, fields_changed=len(changed))
    return n_checks + n_id, changed


def confirm_outsider(ex, frames, t, duration, tr):
    """Кандидат «посторонний»: на 4 кадрах (t…t+6 с) хотя бы на двух стоят ≥ 2 человек. Клиент садится, посторонний стоит."""
    ts = [t + d for d in (0, 2, 4, 6) if t + d <= duration]
    path_at = lambda x: min(frames, key=lambda f: abs(f['t'] - x))['path']
    def ask_people(x):
        a, *_ = chat(CFG['base_url'], CFG['model'], ZSYSTEM, PEOPLE_Q, [path_at(x)], PEOPLE_SCHEMA, CFG['structured'], CFG['max_side'])
        return a or {}
    answers = list(ex.map(ask_people, ts))
    ok = sum((a.get('people_standing') or 0) >= 2 for a in answers) >= 2
    tr.confirm('outsider', t, list(zip(ts, answers)), [path_at(x) for x in ts], ok)
    return ok, len(ts)


# ---------------- основной вызов ----------------
def analyze(video_path, progress=lambda stage, frac: None, dump_states=None, trace_dir=None, video_name=None):
    """Возвращает (result_по_ТЗ, debug). dump_states — путь .jsonl для сохранения таймлайна (подбор порогов без GPU);
    trace_dir — папка трассы (index.html + картинки с рамками), обновляется по ходу обработки."""
    tr = Tracer(trace_dir if CFG['trace'] else None, video_name or os.path.basename(video_path))
    try:
        return _analyze(video_path, progress, dump_states, tr)
    except Exception as e:
        tr.finish(error=f'{type(e).__name__}: {e}'); raise


def _analyze(video_path, progress, dump_states, tr):
    t0 = time.time()
    _progress = progress

    def progress(stage, frac):                       # шаг трассы = этап прогресса (без счётчиков в скобках)
        _progress(stage, frac)
        base = stage.split(' (')[0]
        if base != tr.data['stage']: tr.step(base)
    progress('Подготовка видео', 0.02)
    duration = probe_duration(video_path)
    with tempfile.TemporaryDirectory(prefix='cashdesk_') as tmp:
        frames = extract_frames(video_path, tmp, fps=2.0, long_side=CFG['frame_long_side'])
        if not duration and frames: duration = frames[-1]['t']
        picked, step = plan_frames(frames, duration)
        tr.note(duration_s=round(duration, 1), frames_2fps=len(frames), planned=len(picked), step_s=round(step, 2))
        det, aspect = None, 1.0
        if CFG['detector'] and people.AVAILABLE and frames:
            progress('Детектор людей', 0.05)
            t_det = time.time(); det = people.detect_frames(frames)
            with Image.open(frames[0]['path']) as im0: aspect = im0.width / im0.height
            tr.note(frames=len(frames), ms_per_frame=round(1000 * (time.time() - t_det) / len(frames), 1),
                    max_persons=max((len(v) for v in det.values()), default=0))

        # пропуск неизменившихся кадров
        jobs, reuse_of, last_th, last_t = [], {}, None, -1e9
        for f in picked:
            th = thumb(f['path'])
            if last_th is not None and float(np.abs(th - last_th).mean()) < CFG['diff_thr'] and f['t'] - last_t < CFG['max_gap']:
                reuse_of[f['t']] = last_t
            else:
                jobs.append(f); last_th, last_t = th, f['t']
        progress(f'Анализ кадров моделью ({len(jobs)} из {len(picked)})', 0.08)

        results, done = {}, 0
        n_zoom, n_changed, n_confirm, boxes, dropped = 0, 0, 0, {}, []
        with ThreadPoolExecutor(CFG['workers']) as ex:
            loc_fut = ex.submit(Z.locate, [picked[0]['path'], picked[len(picked) // 2]['path']], CFG_Z, ZSYSTEM) \
                if CFG['zoom'] and picked else None
            for r in ex.map(ask, jobs):
                results[r['t']] = r; done += 1
                progress(f'Анализ кадров моделью ({done}/{len(jobs)})', 0.08 + 0.7 * done / max(1, len(jobs)))

            samples = []
            for f in picked:
                src = results.get(f['t']) or results.get(reuse_of.get(f['t']))
                if src and src['ok']:
                    samples.append({'t': f['t'], 'state': dict(src['state'])})

            by_path = {f['t']: f['path'] for f in frames}
            tr.note(sent=len(jobs), reused=len(picked) - len(jobs), ok=sum(r['ok'] for r in results.values()),
                    mean_latency_s=round(sum(r['latency_s'] for r in results.values()) / max(1, len(results)), 2))
            zoom_changes = []
            if loc_fut:
                boxes = loc_fut.result() or {}
                tr.room = lambda p: people.in_room(p, boxes)
                tr.boxes(picked[0]['path'], boxes, (det or {}).get(picked[0]['t']))
            tr.frames(picked, jobs, reuse_of, results, by_path, det)
            if loc_fut:
                n_zoom, zoom_changes = zoom_pass(ex, samples, frames, boxes, duration, progress, tr)
                n_changed = len(zoom_changes)

            progress('Проверка правил и норм', 0.92)
            V, obs = detect(samples, {}, experimental=False)
            ppl = None
            if det is not None:          # люди — по детектору, а не по анкете 4B
                ppl = people.per_second(det, boxes, aspect, duration)
                coll = lambda sec: any(abs(x['t'] - sec) <= 1.5 and x['state']['collector_present'] for x in samples)
                V = sorted([v for v in V if v['rule'] not in ('outsider', 'two_clients')] + people.events(*ppl, coll), key=lambda v: v['t'])
            # действия кассира — 8B по окнам из 4 кадров в моменты, найденные детектором (после всех запросов 4B)
            act_windows = []
            if actions.MODEL and ppl is not None:
                wins, _ = actions.plan(*ppl, samples, duration)
                if wins:
                    progress(f'Действия кассира ({len(wins)} окон, {actions.MODEL})', 0.93)
                    with ThreadPoolExecutor(CFG['action_workers']) as ex2:
                        res8 = list(ex2.map(lambda w: actions.ask(frames, w[0], CFG['base_url'], CFG['structured'], ZSYSTEM), wins))
                    for (w0, why, sid), (ans, ps, lat) in zip(wins, res8):
                        act_windows.append({'t0': w0, 'why': why, 'session': sid, 'answer': ans, 'latency_s': round(lat, 1)})
                        tr.action(w0, why, ans, ps, lat)
                    tr.note(windows=len(wins), mean_latency_s=round(sum(w['latency_s'] for w in act_windows) / len(wins), 1))
                    V = sorted(V + actions.rules(act_windows), key=lambda v: v['t'])
            tr.note(candidates=[f"{v['rule']}@{v['t']}" for v in V])
            if CFG['zoom'] and det is None and any(v['rule'] == 'outsider' for v in V):
                progress('Подтверждение кандидатов', 0.94)
                kept = []
                for v in V:
                    if v['rule'] == 'outsider':
                        ok, n = confirm_outsider(ex, frames, v['t'], duration, tr); n_confirm += n
                        if not ok: dropped.append(f"outsider@{v['t']}"); continue
                    kept.append(v)
                V = kept
            tr.timeline(samples, V, {(st, f) for st, f, _ in zoom_changes}, ppl)

        if dump_states:
            side = {'n': ppl[0] if ppl else None, 's': ppl[1] if ppl else None, 'boxes': boxes, 'actions': act_windows}
            json.dump(side, open(dump_states[:-6] + '.side.json', 'w', encoding='utf-8'), ensure_ascii=False)
            with open(dump_states, 'w', encoding='utf-8') as fds:
                for smp in samples:
                    fds.write(json.dumps({'video': os.path.splitext(os.path.basename(dump_states))[0], 't': smp['t'], 'state': smp['state'], 'ok': True,
                                          'latency_s': (results.get(smp['t']) or {}).get('latency_s', 0), 'reused': smp['t'] not in results},
                                         ensure_ascii=False) + '\n')
        out = to_output('video', V, obs, CODEX)
        progress('Кадры-доказательства', 0.97)

        violations = []
        by_t = {f['t']: f['path'] for f in frames}
        for v in out['violations']:
            if v.get('needs_verify'):          # правила без примеров в датасете — в ответ не идут без подтверждения
                continue
            ev = []
            for t in v['evidence_t']:
                tt = min(by_t, key=lambda x: abs(x - t))
                ev.append({'timestamp_sec': round(tt, 2), 'image_base64': b64_jpeg(by_t[tt])})
            n = v['norm']
            strength = 'прямая норма' if n.get('strength') == 'direct' else 'косвенная норма'
            ev_imgs = [tr.evidence(len(violations), v['rule'], v['type'], e['timestamp_sec'], by_t[e['timestamp_sec']], boxes,
                                   (det or {}).get(e['timestamp_sec']) if v['rule'] in ('outsider', 'two_clients', 'client_left_count') else None) for e in ev]
            violations.append({
                'type': v['type'],
                'timecode_sec': v['timecode_sec'],
                'description': f"{v['description']} Основание: {act_name(n.get('act'))}, {n.get('punkt')} ({strength}). "
                               'Это подсказка для проверки человеком, а не окончательный вывод.',
                'evidence_frames': ev,
                'norm': {'id': n.get('id'), 'document': act_name(n.get('act')), 'punkt': n.get('punkt'),
                         'quote': n.get('quote'), 'url': n.get('url'), 'strength': n.get('strength')},
                '_evidence_imgs': [x for x in ev_imgs if x],
            })
        result = {'verdict': 'violation' if violations else 'no_violation', 'violations': violations}
        debug = {'duration_s': round(duration, 1), 'step_s': round(step, 2), 'frames_planned': len(picked),
                 'vlm_calls': len(jobs), 'vlm_ok': sum(r['ok'] for r in results.values()),
                 'zoom_checks': n_zoom, 'zoom_changed': n_changed, 'confirm_calls': n_confirm, 'dropped': dropped,
                 'detector': people.MODEL_ID if det is not None else None,
                 'action_calls': len(act_windows), 'action_model': actions.MODEL if act_windows else None,
                 'boxes': boxes, 'mean_latency_s': round(sum(r['latency_s'] for r in results.values()) / max(1, len(results)), 2),
                 'processing_s': round(time.time() - t0, 1), 'model': CFG['model'],
                 'rules': [{k: v[k] for k in ('rule', 'type', 'timecode_sec', 'codex_ids', 'needs_verify')} for v in out['violations']]}
        tr.finish(result, debug, rules=debug['rules'], dropped=dropped)
        for v in result['violations']: v.pop('_evidence_imgs', None)          # в ответ API не идёт
        return result, debug


ACTS = {'231': 'Правила НБРК № 231 (кассовые операции и инкассация)', '14': 'Правила НБРК № 14 (охрана и устройство помещений)',
        '230': 'Правила НБРК № 230 (платёжность банкнот)', '49': 'Правила НБРК № 49 (обменные операции)',
        '53': 'Требования ИБ АРРФР № 53', 'AML': 'Закон РК о ПОД/ФТ № 191-IV', 'BANKS': 'Закон РК о банках № 258-VIII',
        'PD': 'Закон РК о персональных данных'}


def act_name(a):
    return ACTS.get(a, a or '')


if __name__ == '__main__':
    res, dbg = analyze(sys.argv[1], progress=lambda s, f: print(f'[{f:4.0%}] {s}', flush=True))
    slim = {**res, 'violations': [{**v, 'evidence_frames': [{'timestamp_sec': e['timestamp_sec'], 'image_base64': e['image_base64'][:24] + '…'}
                                                            for e in v['evidence_frames']]} for v in res['violations']]}
    print(json.dumps(slim, ensure_ascii=False, indent=1)); print(json.dumps(dbg, ensure_ascii=False))
