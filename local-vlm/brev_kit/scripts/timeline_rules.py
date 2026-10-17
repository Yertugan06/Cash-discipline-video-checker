"""Таймлайн состояний → события → правила → кандидаты-нарушения с таймкодом и ID нормы из кодекса.
Норма НИКОГДА не генерируется: берётся из codex_verified.json по ID.

python scripts/timeline_rules.py --states runs/q35_9b/states --out runs/q35_9b/violations
python scripts/timeline_rules.py ... --params my_params.json      # подбор порогов
python scripts/timeline_rules.py ... --experimental               # включить экспериментальные правила
"""
import argparse, glob, json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_codex

P = {  # пороги (секунды) — подбирать на 40 роликах через eval_videos.py
    'smooth_k': 1,              # окно сглаживания ±k отсчётов
    'min_away_s': 3.0,          # кассир отсутствует за столом не меньше
    'leave_anchor': 'desk',     # таймкод ухода: desk = встала из-за стола, room = вышла из комнаты
    'safe_open_s': 8.0,         # сейф открыт, а кассир не у сейфа, дольше (кассир, сидя у сейфа, открывает его на 3–6 с — это норма)
    'door_check': (3.0, 9.0),   # окно после входа кассира, в котором дверь должна закрыться
    'outsider_s': 3.0,          # второй человек на стороне кассира (при пустой клиентской стороне) дольше
    'personal_s': 12.0,         # личные вещи на столе дольше
    'phone_s': 4.0,             # телефон в руке кассира дольше
    'collector_quick_s': 6.0,   # инкассатор ушёл быстрее чем через N с после сумки на столе
    'min_samples': 2,           # минимальная длина «устойчивого» состояния в отсчётах
    'session_gap_s': 2.5,       # склейка разрывов в присутствии клиента
    'dedupe_s': 10.0,           # одинаковые правила ближе N с — одно нарушение
}
NEEDS_VERIFY = {'phone', 'no_id'}   # phone — нет примеров; no_id — 4B не видит удостоверение (7 из 7 срабатываний ложные, проверено вручную)

TITLE = {
    'leave_cash': 'Наличные/ценности оставлены без присмотра: кассир покинул рабочее место',
    'leave_key': 'Ключ оставлен в замке сейфа',
    'leave_laptop': 'Рабочее место (ноутбук) оставлено незаблокированным',
    'leave_docs': 'Документы/носители оставлены на столе при уходе',
    'safe_open': 'Сейф (хранилище) оставлен открытым',
    'dirty_desk': 'Деньги предыдущего клиента не убраны при обслуживании следующего',
    'merge_cash': 'Наличные разных клиентов смешаны на рабочем месте',
    'two_clients': 'Одновременное обслуживание нескольких клиентов',
    'outsider': 'Посторонний в кассовой кабине',
    'door_open': 'Дверь кассы не закрыта',
    'client_left_count': 'Пересчёт денег не в присутствии клиента (клиент ушёл)',
    'no_id': 'Приём наличных без предъявления документа клиентом',
    'personal_items': 'Личные вещи на рабочем месте кассира',
    'food': 'Еда/напитки на рабочем месте кассира',
    'phone': 'Телефон в руках кассира в кассовом узле',
    'collector_quick': 'Сумка от инкассатора принята без проверки (инкассатор сразу ушёл)',
    'bag_to_safe_no_count': 'Деньги из вскрытой сумки убраны в сейф без пересчёта',
    'no_detector': 'Пересчёт без проверки подлинности на детекторе',
}
CODEX = {
    'leave_cash': ['231-20-2', '231-22'], 'leave_key': ['231-80-1'], 'leave_laptop': ['53-71-9'], 'leave_docs': ['231-80-3'],
    'safe_open': ['231-20-2b'], 'dirty_desk': ['231-20-2'], 'merge_cash': ['231-20-2', '231-21'], 'two_clients': ['231-20-2', '231-21'],
    'outsider': ['14-16-1', '14-8-1'], 'door_open': ['14-16-1', '14-8-1'], 'client_left_count': ['231-20-1'],
    'no_id': ['231-19-1', '231-7'], 'personal_items': ['231-12-1'], 'food': ['231-12-2'], 'phone': ['231-12-2b'],
    'collector_quick': ['231-24-3', '231-24-4'], 'bag_to_safe_no_count': ['231-74-1', '231-42'], 'no_detector': ['231-19-2b'],
}
VERIFY_Q = {
    'leave_cash': 'Is the cashier away from the desk while banknotes or a cash bag remain on the desk?',
    'leave_key': 'After the cashier walks away, is a key left sticking out of the safe lock?',
    'leave_laptop': 'After the cashier walks away, does the laptop show an unlocked working screen (not a lock screen, not closed)?',
    'leave_docs': 'After the cashier walks away, are documents, a folder or a tablet left on the desk?',
    'safe_open': 'Is the safe door left open while the cashier is not standing at the safe?',
    'dirty_desk': 'Does a new client arrive while banknotes from the previous operation still lie on the desk?',
    'merge_cash': 'Does the cashier put the new client\'s banknotes together with banknotes that were already on the desk?',
    'two_clients': 'Are two different clients being served at the desk at the same time?',
    'outsider': 'Is a person other than the cashier (not a client at the client side) inside the cashier zone?',
    'door_open': 'Is the cash room door left open while the cashier works at the desk?',
    'client_left_count': 'Does the client walk away while his banknotes are still being counted?',
    'no_id': 'Did the client hand over cash without showing any ID document first?',
    'personal_items': 'Are personal items (coat, handbag, backpack) on the cashier\'s desk?',
    'food': 'Is the cashier eating or drinking at the cash desk, or food/drink on the desk?',
    'phone': 'Is the cashier holding or using a mobile phone?',
    'collector_quick': 'Does the cash collector leave right after putting the bag on the desk, without the bag being inspected together?',
    'bag_to_safe_no_count': 'Are banknote bundles taken from the bag put into the safe without being counted?',
    'no_detector': 'Are banknotes counted by hand without being checked on the banknote detector?',
}
EXPERIMENTAL = {'no_detector'}


def smooth(samples, k):
    """Мажоритарное сглаживание по каждому полю (bool/enum — мода, int — медиана)."""
    out = []
    for i, s in enumerate(samples):
        win = [x['state'] for x in samples[max(0, i - k): i + k + 1]]
        st = {}
        for f, v in s['state'].items():
            vals = [w.get(f) for w in win if w.get(f) is not None]
            if f == 'other': st[f] = v
            elif isinstance(v, int) and not isinstance(v, bool): st[f] = sorted(vals)[len(vals) // 2]
            else: st[f] = Counter(vals).most_common(1)[0][0]
        out.append({'t': s['t'], 'state': st})
    return out


def runs(S, pred, min_len=1):
    """Непрерывные отрезки, где pred(state) истинно: [(i_start, i_end)]."""
    res, i = [], 0
    while i < len(S):
        if pred(S[i]['state']):
            j = i
            while j + 1 < len(S) and pred(S[j + 1]['state']): j += 1
            if j - i + 1 >= min_len: res.append((i, j))
            i = j + 1
        else: i += 1
    return res


def frac(S, i0, i1, pred):
    seg = S[max(0, i0): max(0, i1) + 1]
    return sum(pred(x['state']) for x in seg) / max(1, len(seg))


def idx_at(S, t):
    return min(range(len(S)), key=lambda i: abs(S[i]['t'] - t))


def detect(samples, params, experimental=False):
    p = {**P, **(params or {})}
    S = smooth(samples, p['smooth_k'])
    if not S: return [], []
    dt = (S[-1]['t'] - S[0]['t']) / max(1, len(S) - 1) or 1.0
    n = lambda sec: max(1, round(sec / dt))
    ms = p['min_samples']; V = []

    def add(rule, i, extra=''):
        V.append({'rule': rule, 't': S[i]['t'], 'i': i, 'extra': extra})

    # --- уход кассира с рабочего места
    for i0, i1 in runs(S, lambda s: not s['cashier_at_desk'], n(p['min_away_s'])):
        if i0 == 0: continue                                   # не было за столом в начале — это не уход
        exits = [k for k in range(i0, i1 + 1) if not S[k]['state']['cashier_in_room']]
        anchor = exits[0] if (p['leave_anchor'] == 'room' and exits) else i0
        if exits:                                              # деньги/сумка на столе, когда кассир ВЫШЛА из комнаты (у сейфа в комнате — норма)
            if frac(S, max(i0, exits[0] - n(2)), min(i1, exits[0] + n(3)), lambda s: s['desk_cash'] or s['desk_bag']) >= 0.5:
                add('leave_cash', anchor)
        if exits:
            e0, e1 = exits[0], min(i1, exits[0] + n(3))
            if frac(S, e0, e1, lambda s: s['key_in_safe_lock'] == 'yes') >= 0.5:
                at_safe = [k for k in range(i0 - n(5), exits[0]) if k >= 0 and S[k]['state']['cashier_action'] == 'at_safe']
                add('leave_key', at_safe[-1] if at_safe else exits[0])
            if frac(S, e0, e1, lambda s: s['desk_documents']) >= 0.5:
                add('leave_docs', anchor)
        if exits and frac(S, exits[0], i1, lambda s: s['laptop_screen'] == 'unlocked') >= 0.6:   # вышла из комнаты, экран рабочий
            add('leave_laptop', anchor)

    # --- сейф открыт, а кассир не у сейфа
    for i0, i1 in runs(S, lambda s: s['safe_door'] == 'open' and s['cashier_action'] != 'at_safe', n(p['safe_open_s'])):
        add('safe_open', i0)

    # --- сессии клиентов
    sess = runs(S, lambda s: s['clients_at_desk'] >= 1, ms)
    merged = []
    for a, b in sess:
        if merged and S[a]['t'] - S[merged[-1][1]]['t'] <= p['session_gap_s']: merged[-1] = (merged[-1][0], b)
        else: merged.append((a, b))
    for k, (a, b) in enumerate(merged):
        start = a
        for j in range(max(0, a - n(4)), a):                   # момент входа, если видно «человек в двери»
            if S[j]['state']['person_at_door']: start = j; break
        # деньги на столе к моменту прихода нового клиента (окно захватывает и первые секунды после прихода)
        if k > 0 and frac(S, max(0, start - n(3)), min(b, a + n(2)), lambda s: s['desk_cash']) >= 0.5:
            add('dirty_desk', start)
            for j in range(a, b + 1):
                s = S[j]['state']
                if s['cashier_action'] in ('receiving_cash', 'counting_by_hand') or s['cash_in_hands_of'] in ('client', 'several'):
                    if S[j]['t'] - S[start]['t'] >= 3: add('merge_cash', j)
                    break
        t_cash = next((j for j in range(a, b + 1) if S[j]['state']['cash_in_hands_of'] in ('client', 'several')
                       or S[j]['state']['cashier_action'] == 'receiving_cash'), None)
        id_seen = any(S[j]['state']['id_document_visible'] or S[j]['state']['cashier_action'] == 'checking_id_document'
                      for j in range(max(0, start - n(2)), b + 1))      # документ за всю сессию, не только до денег
        if t_cash is not None and not id_seen and S[b]['t'] - S[a]['t'] >= 8:
            add('no_id', t_cash)
        end = b + 1
        if end < len(S) and frac(S, max(0, end - n(3)), min(len(S) - 1, end + n(2)),
                                 lambda s: s['counting_machine_in_use'] or s['cashier_action'] in ('using_counting_machine', 'counting_by_hand')) >= 0.5:
            add('client_left_count', end)

    for i0, i1 in runs(S, lambda s: s['clients_at_desk'] >= 2 and not s['collector_present'], ms): add('two_clients', i0)
    # посторонний: второй человек на стороне кассира, когда клиентская сторона пуста (иначе это почти всегда неверно посчитанный клиент)
    for i0, i1 in runs(S, lambda s: s['people_cashier_side'] >= 2 and not s['collector_present'] and not s['person_at_door'], n(p['outsider_s'])):
        if frac(S, max(0, i0 - n(3)), max(0, i0 - 1), lambda s: s['clients_at_desk'] == 0) >= 0.6:   # до этого клиентов не было
            add('outsider', i0)
    # дверь: после ВХОДА кассира дверь остаётся открытой, хотя через неё никто не проходит
    entries = [j for j in range(1, len(S)) if S[j]['state']['cashier_at_desk'] and not S[j - 1]['state']['cashier_at_desk']
               and any(not S[k]['state']['cashier_in_room'] or S[k]['state']['person_at_door'] for k in range(max(0, j - n(6)), j))]
    for j in entries:
        w0, w1 = j + n(p['door_check'][0]), min(len(S) - 1, j + n(p['door_check'][1]))
        if w0 < w1 and frac(S, w0, w1, lambda s: s['room_door'] == 'open' and not s['person_at_door']) >= 0.6:
            add('door_open', min(len(S) - 1, j + n(2)))
    for i0, i1 in runs(S, lambda s: s['desk_personal_items'], n(p['personal_s'])):
        at = next((k for k in range(i0, i1 + 1) if S[k]['state']['cashier_at_desk']), i0)       # вещи уже на рабочем месте
        add('personal_items', at)
    # еда: нужен сам факт еды/питья, а не просто стакан на столе (стакан бывает и в «чистых» роликах)
    for i0, i1 in runs(S, lambda s: s['desk_food_drink'] or s['cashier_action'] == 'eating_drinking', ms):
        ate = any(S[k]['state']['cashier_action'] == 'eating_drinking' for k in range(i0, i1 + 1))
        appeared = S[i0]['t'] - S[0]['t'] > 3 and i1 - i0 + 1 >= n(5)      # еда/напиток появились по ходу видео и держатся
        if ate or appeared: add('food', i0)
    for i0, i1 in runs(S, lambda s: s['phone_in_cashier_hand'] or s['cashier_action'] == 'using_phone', n(p['phone_s'])): add('phone', i0)

    # --- инкассатор: сумка на столе, инкассатор быстро ушёл
    for i0, i1 in runs(S, lambda s: s['collector_present'], 1):
        bag = next((j for j in range(i0, i1 + 1) if S[j]['state']['desk_bag']), None)
        if bag is not None and S[i1]['t'] - S[bag]['t'] <= p['collector_quick_s'] and i1 + 1 < len(S):
            add('collector_quick', bag)

    # --- сумка вскрыта → сейф открыт, без пересчёта между
    opened = [j for j in range(len(S)) if S[j]['state']['cashier_action'] == 'packing_or_opening_bag']
    if opened:
        for j in range(opened[0], len(S)):
            if S[j]['state']['safe_door'] == 'open' or S[j]['state']['cashier_action'] == 'at_safe':
                counted = any(S[k]['state']['counting_machine_in_use'] or S[k]['state']['cashier_action'] in ('counting_by_hand', 'using_counting_machine')
                              for k in range(opened[0], j))
                if not counted: add('bag_to_safe_no_count', j)
                break

    if experimental:
        hand = [j for j in range(len(S)) if S[j]['state']['cashier_action'] == 'counting_by_hand']
        if hand and not any(s['state']['detector_in_use'] or s['state']['cashier_action'] == 'using_detector' for s in S):
            add('no_detector', hand[0])

    # --- дедупликация одинаковых правил
    V.sort(key=lambda v: v['t']); out = []
    for v in V:
        if any(o['rule'] == v['rule'] and abs(o['t'] - v['t']) < p['dedupe_s'] for o in out): continue
        out.append(v)
    obs = [{'t': s['t'], 'other': s['state'].get('other', '')} for s in samples if (s['state'].get('other') or '').strip()]
    return out, obs


def to_output(vid, V, obs, codex):
    viol = []
    for v in V:
        ids = CODEX[v['rule']]; c = codex.get(ids[0], {})
        viol.append({
            'rule': v['rule'], 'type': TITLE[v['rule']], 'timecode_sec': round(v['t'], 2), 'codex_ids': ids,
            'evidence_t': [round(max(0, v['t'] - 1), 2), round(v['t'], 2), round(v['t'] + 1, 2)],
            'verify_question': VERIFY_Q[v['rule']], 'needs_verify': v['rule'] in NEEDS_VERIFY,
            'description': f"{TITLE[v['rule']]} (по кадрам около {v['t']:.1f} с).",
            'norm': {'id': ids[0], 'act': c.get('act'), 'punkt': c.get('punkt'), 'quote': c.get('quote'),
                     'url': c.get('url'), 'strength': c.get('strength')},
        })
    confirmed = [v for v in viol if not v['needs_verify']]
    return {'video': vid, 'verdict': 'violation' if confirmed else 'no_violation', 'violations': viol, 'observations': obs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--states', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--params'); ap.add_argument('--codex'); ap.add_argument('--experimental', action='store_true')
    a = ap.parse_args()
    params = json.load(open(a.params, encoding='utf-8')) if a.params else {}
    codex = load_codex(a.codex); os.makedirs(a.out, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(a.states, '*.jsonl'))):
        rows = [json.loads(l) for l in open(p, encoding='utf-8')]
        samples = [{'t': r['t'], 'state': r['state']} for r in rows if r.get('ok') and isinstance(r.get('state'), dict)]
        samples.sort(key=lambda s: s['t'])
        vid = rows[0]['video'] if rows else os.path.basename(p)[:-6]
        V, obs = detect(samples, params, a.experimental)
        res = to_output(vid, V, obs, codex)
        json.dump(res, open(os.path.join(a.out, f'{vid}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(vid, res['verdict'], [(v['rule'], v['timecode_sec']) for v in res['violations']])


if __name__ == '__main__':
    main()
