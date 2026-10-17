"""Действия кассира по окнам из 4 кадров (1 кадр/с) — отдельная, более сильная модель (Qwen3-VL 8B).

4B по одному кадру и даже по окну не различает, как кассир считает деньги и ушёл ли клиент; 8B различает
(X-44/X-45 — детектор, X-1/X-3 — пересчёт руками, X-34 — клиент ушёл, деньги у кассира).
На ноутбуке с 6 ГБ 8B частично выгружается в ОЗУ: ~5 с на окно + ~30 с первая загрузка, поэтому окон мало
и только в моменты событий, найденных детектором людей:
  leave   — во время сессии кто-то встал, новых людей не прибавилось (клиент уходит);
  session — до 2 окон внутри каждой сессии с клиентом (≥ 2 человек в комнате ≥ 4 с);
  cash    — кассир работает с деньгами без клиента (по анкете 4B деньги в руках у кассира ≥ 3 с): до 2 окон на эпизод.
Правила:
  client_left_count — в окне ухода идёт пересчёт, клиента в конце нет, деньги у кассира (Правила № 231, п. 20 ч. 1);
  no_detector       — в сессии считали только руками и ни разу не положили купюры на детектор (п. 19 пп. 2).
"""
import json, os, threading, urllib.request

from common import chat

MODEL = os.environ.get('ACTION_MODEL', 'qwen3-vl:8b-instruct')     # '' — выключить
MAX_WINDOWS = int(os.environ.get('ACTION_MAX_WINDOWS', '4'))
SIDE = 768

SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['counting', 'detector_used', 'client_present_start', 'client_present_end', 'cash_with_cashier'],
          'properties': {'counting': {'type': 'string', 'enum': ['machine', 'by_hand', 'both', 'none']},
                         'detector_used': {'type': 'boolean'},
                         'client_present_start': {'type': 'boolean'}, 'client_present_end': {'type': 'boolean'},
                         'cash_with_cashier': {'type': 'boolean'}}}
Q = ('These 4 images are consecutive frames, 1 second apart, from an overhead camera at a bank cash desk. Watch ALL frames:\n'
     '- counting: how the cashier counts banknotes in these seconds: machine (feeds notes into the counting machine), '
     'by_hand (flips notes by hand), both, or none;\n'
     '- detector_used: the cashier places banknotes on / under the small banknote detector (UV device) at any moment;\n'
     '- client_present_start / client_present_end: a client is at the client side of the desk in the FIRST / in the LAST frame;\n'
     '- cash_with_cashier: the cashier holds banknotes or banknotes are in the counting machine in the last frame.')


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


def plan(n, s, samples, duration):
    """Окна [(t0, причина, сессия)] — t0: первый кадр окна (окно t0 … t0+3 с)."""
    at_desk = lambda a, b: [x['state']['cashier_at_desk'] for x in samples if a <= x['t'] <= b]
    sessions = [(i, j) for i, j in _runs(n, lambda v: v >= 2, 4)]
    wins, last = [], -99
    for k in range(3, len(n) - 1):
        if min(n[k - 3:k]) >= 2 and max(s[k - 2:k]) == 0 and min(s[k:k + 2]) >= 1 and max(n[k:k + 2]) <= max(n[k - 3:k]) and k - last > 5:
            d = at_desk(k, k + 3)
            if d and sum(d) / len(d) >= 0.5:
                sid = next((m for m, (i, j) in enumerate(sessions) if i <= k <= j + 1), None)
                wins.append((max(0.0, k - 1.0), 'leave', sid)); last = k
    for m, (i, j) in enumerate(sessions):
        lo, hi = i + 1, max(i + 1, j - 3)
        for t0 in sorted({lo, round((lo + hi) / 2)}):
            if t0 + 3 <= duration and all(abs(t0 - w[0]) >= 3 for w in wins):
                wins.append((float(t0), 'session', m))
    # эпизоды «кассир с деньгами» вне сессий с клиентом
    T = len(n)
    cash = [any(x['state'].get('cash_in_hands_of') in ('cashier', 'several') for x in samples if k <= x['t'] < k + 1.5) for k in range(T)]
    in_sess = [any(i <= k <= j for i, j in sessions) for k in range(T)]
    for m, (i, j) in enumerate(_runs([c and not q for c, q in zip(cash, in_sess)], bool, 3)):
        lo, hi = i + 1, max(i + 1, j - 3)
        for t0 in sorted({lo, round((lo + hi) / 2)}):
            if t0 + 3 <= duration and all(abs(t0 - w[0]) >= 3 for w in wins):
                wins.append((float(t0), 'cash', 100 + m))
    prio = {'leave': 0, 'session': 1, 'cash': 2}
    wins.sort(key=lambda w: (prio[w[1]], w[0]))
    return sorted(wins[:MAX_WINDOWS]), sessions


def ask(frames, t0, base_url, structured, system):
    path_at = lambda x: min(frames, key=lambda f: abs(f['t'] - x))['path']
    ps = [path_at(t0 + k) for k in range(4)]
    ans, raw, lat, err = chat(base_url, MODEL, system, Q, ps, SCHEMA, structured, SIDE)
    return ans or {}, ps, lat


def _ollama(base_url, body):
    root = base_url.rstrip('/').removesuffix('/v1')
    req = urllib.request.Request(root + '/api/generate', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=120).read()
    except Exception as e:                          # noqa: BLE001 — прогрев необязателен, ошибка не должна ронять анализ
        print('[actions] ollama', body.get('model'), type(e).__name__, e, flush=True)


def swap_back(base_url, main_model):
    """Выгрузить 8B сразу (освободить видеопамять) и в фоне загрузить основную 4B."""
    _ollama(base_url, {'model': MODEL, 'keep_alive': 0})
    threading.Thread(target=_ollama, args=(base_url, {'model': main_model, 'keep_alive': '30m'}), daemon=True).start()


def rules(windows):
    """windows: [{'t0', 'why', 'session', 'answer'}] → [{'rule', 't', 'i', 'extra'}]."""
    ev = []
    for w in windows:
        a = w['answer']
        if w['why'] == 'leave' and a.get('counting') not in (None, 'none') and a.get('client_present_end') is False \
                and a.get('cash_with_cashier'):
            ev.append({'rule': 'client_left_count', 't': w['t0'] + 1, 'i': None, 'extra': f"пересчёт: {a.get('counting')}, клиента нет"})
    by_s = {}
    for w in windows:
        if w['session'] is not None: by_s.setdefault(w['session'], []).append(w)
    for sid, ws in by_s.items():
        hand = [w for w in ws if w['answer'].get('counting') == 'by_hand']
        if hand and not any(w['answer'].get('detector_used') for w in ws):
            ev.append({'rule': 'no_detector', 't': hand[0]['t0'] + 1, 'i': None, 'extra': 'считали руками, детектор не использован'})
    return ev
