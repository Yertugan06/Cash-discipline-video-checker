"""Итоговая оценка как у жюри: вердикт по видео, попадание таймкода, тип (ID нормы), скорость.

python scripts/eval_videos.py --violations runs/q35_9b/violations --run-meta runs/q35_9b/run_meta.json --out runs/q35_9b/report_videos.md
"""
import argparse, csv, glob, json, os
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--violations', required=True)
    ap.add_argument('--gt', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'gt_violations.csv'))
    ap.add_argument('--videos', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'videos.csv'))
    ap.add_argument('--run-meta'); ap.add_argument('--tol', type=float, default=3.0)
    ap.add_argument('--only-verified', action='store_true', help='учитывать только нарушения, которые VLM подтвердила (verify_candidates.py)')
    ap.add_argument('--out')
    a = ap.parse_args()

    vids = [r for r in csv.DictReader(open(a.videos, encoding='utf-8'), delimiter=';') if not r['duplicate_of']]
    gt = defaultdict(list)
    for r in csv.DictReader(open(a.gt, encoding='utf-8'), delimiter=';'):
        gt[r['video']].append({'t': float(r['t']), 'ids': r['expected_codex_ids'].split('|'), 'type': r['type_ru']})
    pred = {}
    for p in glob.glob(os.path.join(a.violations, '*.json')):
        d = json.load(open(p, encoding='utf-8'))
        vs = d['violations']
        if a.only_verified: vs = [v for v in vs if v.get('verified', 'yes') != 'no']
        pred[d['video']] = vs

    TP = FP = TN = FN = 0; rows = []; matched = {1: 0, 3: 0, 5: 0}; n_labels = 0
    tc_err = []; type_ok = 0; type_n = 0; extra_events = 0; missing_pred = []
    for v in vids:
        vid = v['video']; g = gt.get(vid, []); pv = pred.get(vid)
        if pv is None: missing_pred.append(vid); pv = []
        is_v, said_v = bool(g), bool(pv)
        TP += is_v and said_v; FN += is_v and not said_v; FP += (not is_v) and said_v; TN += (not is_v) and not said_v
        used = set()
        for lab in g:
            n_labels += 1
            cands = sorted(((abs(p['timecode_sec'] - lab['t']), k) for k, p in enumerate(pv) if k not in used))
            for tol in matched:
                if cands and cands[0][0] <= tol: matched[tol] += 1
            if cands and cands[0][0] <= a.tol:
                d, k = cands[0]; used.add(k); tc_err.append(d); type_n += 1
                ok = bool(set(pv[k]['codex_ids']) & set(lab['ids'])); type_ok += ok
                rows.append((vid, lab['t'], pv[k]['timecode_sec'], pv[k]['rule'], 'да' if ok else 'НЕТ', lab['type']))
            else:
                rows.append((vid, lab['t'], '—', '—', '—', lab['type'] + ' (ПРОПУСК)'))
        extra_events += len(pv) - len(used)
        if not is_v and pv:
            rows.append((vid, '—', ', '.join(str(p['timecode_sec']) for p in pv), ', '.join(p['rule'] for p in pv), '—', 'ЛОЖНОЕ СРАБАТЫВАНИЕ (чистое видео)'))

    nv = len(vids)
    L = ['# Оценка по видео', f'Видео: {nv} уникальных (дубликаты X-47/X-48 исключены); меток нарушений: {n_labels}.', '',
         '## Вердикт (критерий 1, 25 баллов)', '| | Сказали «нарушение» | Сказали «нет» |', '|---|---|---|',
         f'| Есть нарушение | TP = {TP} | **FN = {FN}** (пропуск — недопустим) |', f'| Нет нарушения | FP = {FP} | TN = {TN} |', '',
         f'Точность вердикта: **{(TP + TN) / max(1, nv):.0%}**; полнота: **{TP / max(1, TP + FN):.0%}**; ложные на чистых: **{FP / max(1, FP + TN):.0%}**', '',
         '## Таймкод (критерий 2, 15 баллов)',
         f'Метки, найденные в пределах ±1 с: {matched[1]}/{n_labels}; ±3 с: {matched[3]}/{n_labels}; ±5 с: {matched[5]}/{n_labels}.',
         f'Средняя ошибка таймкода (для найденных в ±{a.tol:g} с): {sum(tc_err) / max(1, len(tc_err)):.2f} с.', '',
         '## Тип / норма (критерий 3, 15 баллов)', f'ID нормы совпал с ожидаемым: {type_ok}/{type_n}.', '',
         f'Лишних событий (не совпали ни с одной меткой): {extra_events}.']
    if a.run_meta and os.path.exists(a.run_meta):
        m = json.load(open(a.run_meta, encoding='utf-8')); vv = m.get('videos', {})
        worst = max(vv.items(), key=lambda x: x[1]['wall_s'], default=(None, {'wall_s': 0}))
        L += ['', '## Скорость (лимит 300 с на видео)', f"Модель: {m.get('model')}, шаг {m.get('step')} с, max_side {m.get('max_side')}, workers {m.get('workers')}.",
              f"Среднее время VLM на видео: {sum(x['wall_s'] for x in vv.values()) / max(1, len(vv)):.1f} с; худшее: {worst[0]} — {worst[1]['wall_s']:.1f} с.",
              f"Ответов, не прошедших схему: {sum(x['frames'] - x['ok'] for x in vv.values())} из {sum(x['frames'] for x in vv.values())}."]
    if missing_pred: L += ['', f'Нет файла предсказаний для: {", ".join(missing_pred)} (считаются как «нет нарушения»).']
    L += ['', '## По меткам', '| Видео | Метка, с | Предсказано, с | Правило | ID нормы совпал | Нарушение |', '|---|---|---|---|---|---|']
    L += [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |' for r in rows]
    txt = '\n'.join(L); print(txt)
    if a.out: open(a.out, 'w', encoding='utf-8').write(txt)


if __name__ == '__main__':
    main()
