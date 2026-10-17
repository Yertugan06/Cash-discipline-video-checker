"""Синтетические таймлайны (как будто VLM ответила идеально) для проверки правил и оценки без GPU.
python tests/make_fixture_states.py tests/fixture_states
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mock_vlm_server import BASE

OUT = sys.argv[1] if len(sys.argv) > 1 else 'tests/fixture_states'


def timeline(vid, dur, segments):
    """segments: [(t0, t1, {поле: значение})] — поверх базового «кассир за ноутбуком»."""
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f'{vid}.jsonl'), 'w', encoding='utf-8') as f:
        for t in range(0, dur + 1):
            st = dict(BASE)
            for t0, t1, upd in segments:
                if t0 <= t < t1: st.update(upd)
            f.write(json.dumps({'video': vid, 't': float(t), 'state': st, 'ok': True, 'errors': [], 'latency_s': 0.5}, ensure_ascii=False) + '\n')


away = {'cashier_at_desk': False, 'cashier_action': 'walking_out', 'people_cashier_side': 0}
gone = {'cashier_at_desk': False, 'cashier_in_room': False, 'cashier_action': 'not_present', 'people_cashier_side': 0}
# X-26: считает деньги, в 9 с уходит, пачка остаётся (нарушение 9 с)
timeline('X-26', 19, [(0, 19, {'desk_cash': True}), (9, 19, {'laptop_screen': 'lock_screen'}), (5, 9, {'cashier_action': 'counting_by_hand'}), (9, 13, away), (13, 19, gone)])
# X-27: убирает всё в сейф и уходит, стол чист (норма)
timeline('X-27', 26, [(9, 26, {'laptop_screen': 'lock_screen'}), (10, 19, {'cashier_at_desk': False, 'cashier_action': 'at_safe', 'safe_door': 'open'}), (19, 21, away), (21, 26, gone)])
# X-28: встаёт в 7 с и уходит, ноутбук разблокирован (нарушение 7 с)
timeline('X-28', 16, [(7, 11, away), (11, 16, gone)])
# X-29: блокирует экран и уходит (норма)
timeline('X-29', 17, [(6, 17, {'laptop_screen': 'lock_screen'}), (7, 11, away), (11, 17, gone)])
# X-4: клиент 1 обслужен (8–52), его пачка остаётся; клиент 2 входит в 57, деньги клиента 2 в 66 (нарушения 57 и 68)
timeline('X-4', 72, [(8, 52, {'clients_at_desk': 1, 'id_document_visible': False}), (9, 12, {'id_document_visible': True}),
                     (14, 18, {'cash_in_hands_of': 'client'}), (20, 50, {'desk_cash': True, 'cashier_action': 'counting_by_hand'}),
                     (50, 72, {'desk_cash': True, 'cashier_action': 'seated_idle'}), (56, 58, {'person_at_door': True}),
                     (58, 72, {'clients_at_desk': 1}), (61, 64, {'id_document_visible': True}), (66, 70, {'cash_in_hands_of': 'client', 'cashier_action': 'receiving_cash'})])
# X-5: два клиента подряд, между ними деньги убраны в сейф (норма)
timeline('X-5', 71, [(8, 55, {'clients_at_desk': 1}), (9, 12, {'id_document_visible': True}), (14, 18, {'cash_in_hands_of': 'client'}),
                     (20, 44, {'desk_cash': True}), (45, 51, {'cashier_action': 'at_safe', 'safe_door': 'open', 'cashier_at_desk': False}),
                     (63, 71, {'clients_at_desk': 1}), (64, 66, {'id_document_visible': True})])
print('fixtures ->', OUT)
