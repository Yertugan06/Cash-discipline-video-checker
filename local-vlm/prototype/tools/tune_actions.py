"""Подбор правил действий (8B) без GPU: по сохранённым ответам окон (states/*.side.json) пересчитывает
client_left_count / no_detector в нескольких вариантах и считает метрики как у жюри.

  python prototype/tools/tune_actions.py --run prototype/work/runs/v4
"""
import argparse, copy, glob, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'brev_kit')
sys.path.insert(0, os.path.join(KIT, 'scripts'))
from timeline_rules import CODEX, TITLE   # noqa: E402

ACTION_RULES = ('client_left_count', 'no_detector')


def variant_events(wins, v):
    ev = []
    for w in wins:
        a = w['answer']
        if 'leave' in v['use'] and w['why'] == 'leave' and a.get('client_present_end') is False \
                and (a.get('counting') not in (None, 'none') or not v['leave_need_count']) and (a.get('cash_with_cashier') or not v['leave_need_cash']):
            ev.append(('client_left_count', w['t0'] + 1))
    by = {}
    for w in wins:
        if w['session'] is not None and w['why'] in v['det_from']: by.setdefault(w['session'], []).append(w)
    if 'det' in v['use']:
        for sid, ws in by.items():
            hand = [w for w in ws if w['answer'].get('counting') in v['hand_values']]
            if hand and not any(w['answer'].get('detector_used') for w in ws):
                ev.append(('no_detector', hand[0]['t0'] + 1))
    return ev


VARIANTS = {
    'без действий': {'use': ()},
    'уход клиента (строго)': {'use': ('leave',), 'leave_need_count': True, 'leave_need_cash': True},
    'уход клиента (мягко)': {'use': ('leave',), 'leave_need_count': True, 'leave_need_cash': False},
    'детектор: руками, все окна': {'use': ('det',), 'hand_values': ('by_hand',), 'det_from': ('leave', 'session', 'cash')},
    'детектор: руками, без cash-окон': {'use': ('det',), 'hand_values': ('by_hand',), 'det_from': ('leave', 'session')},
    'детектор: руками или оба': {'use': ('det',), 'hand_values': ('by_hand', 'both'), 'det_from': ('leave', 'session', 'cash')},
    'уход (строго) + детектор (руками)': {'use': ('leave', 'det'), 'leave_need_count': True, 'leave_need_cash': True,
                                          'hand_values': ('by_hand',), 'det_from': ('leave', 'session', 'cash')},
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); a = ap.parse_args()
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    for name, v in VARIANTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            for p in glob.glob(os.path.join(a.run, 'violations', '*.json')):
                d = json.load(open(p, encoding='utf-8')); vid = d['video']
                d['violations'] = [x for x in d['violations'] if x['rule'] not in ACTION_RULES]
                for x in d['violations']:
                    if x['rule'] == 'no_id': x['needs_verify'] = True
                sp = os.path.join(a.run, 'states', vid + '.side.json')
                wins = json.load(open(sp, encoding='utf-8')).get('actions', []) if os.path.exists(sp) else []
                for rule, t in variant_events(wins, {**{'leave_need_count': True, 'leave_need_cash': True, 'hand_values': ('by_hand',),
                                                        'det_from': ('leave', 'session', 'cash')}, **v}):
                    d['violations'].append({'rule': rule, 'type': TITLE[rule], 'timecode_sec': t, 'codex_ids': CODEX[rule], 'needs_verify': False})
                json.dump(d, open(os.path.join(tmp, vid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            rep = subprocess.run([sys.executable, os.path.join(KIT, 'scripts', 'eval_videos.py'), '--violations', tmp],
                                 capture_output=True, text=True, encoding='utf-8', env=env).stdout
            lines = [l for l in rep.splitlines() if l.startswith(('| Есть', '| Нет', 'Точность', 'Метки,', 'ID нормы'))]
            print(f'== {name}\n   ' + '\n   '.join(lines))


if __name__ == '__main__':
    main()
