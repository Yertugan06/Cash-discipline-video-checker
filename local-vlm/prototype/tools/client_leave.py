"""Правило «пересчёт без клиента» (Правила № 231, п. 20 ч. 1): клиент ушёл, а деньги ещё пересчитывают.

Шаг 1 (CPU, по сохранённым рамкам D-FINE и таймлайнам): моменты ухода клиента — людей в комнате стало меньше
(было ≥ 2 не меньше 3 с, стало меньше и держится 3 с), а кассир по анкете остался за столом.
  python prototype/tools/client_leave.py candidates --det prototype/work/runs/dfine --zoom prototype/work/runs/proto_4b/zoom \
      --states prototype/work/runs/proto_4b_v2/states --out prototype/work/runs/leave_candidates.json
Шаг 2 (GPU): по каждому кандидату — вопрос по 4 кадрам (t−1 … t+2): идёт ли пересчёт и есть ли клиент в конце.
  python prototype/tools/client_leave.py ask --videos open/open/videos --cand leave_candidates.json --out leave_answers.json
"""
import argparse, glob, json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

LEAVE_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['counting', 'client_present_end', 'cash_with_cashier'],
                'properties': {'counting': {'type': 'string', 'enum': ['machine', 'by_hand', 'both', 'none']},
                               'client_present_end': {'type': 'boolean'}, 'cash_with_cashier': {'type': 'boolean'}}}
LEAVE_Q = ('These 4 images are consecutive frames, 1 second apart, from an overhead camera at a bank cash desk. Watch ALL frames:\n'
           '- counting: is the cashier counting banknotes in these seconds: machine (notes in / going through the counting machine), '
           'by_hand (flipping notes by hand), both, or none;\n'
           '- client_present_end: is a client still at the client side of the desk in the LAST frame;\n'
           '- cash_with_cashier: does the cashier hold banknotes or are banknotes in the counting machine in the last frame.')


def candidates(a):
    import people
    out = []
    for p in sorted(glob.glob(os.path.join(a.det, 'X-*.jsonl')), key=lambda p: int(os.path.basename(p)[2:-6])):
        vid = os.path.basename(p)[:-6]
        rows = [json.loads(l) for l in open(p, encoding='utf-8')]
        det = {r['t']: r['persons'] for r in rows}
        zp = os.path.join(a.zoom, vid + '.json'); boxes = json.load(open(zp, encoding='utf-8'))['boxes'] if os.path.exists(zp) else {}
        sp = os.path.join(a.states, vid + '.jsonl')
        st = [json.loads(l) for l in open(sp, encoding='utf-8')] if os.path.exists(sp) else []
        dur = rows[-1]['t'] if rows else 0
        n, s = people.per_second(det, boxes, 464 / 848, dur)
        last = -99
        for k in range(3, len(n) - 1):
            # во время сессии (≥ 2 человек 3 с) кто-то встал и стоит ≥ 2 с, а людей не прибавилось — это уход, а не приход
            if min(n[k - 3:k]) >= 2 and max(s[k - 2:k]) == 0 and min(s[k:k + 2]) >= 1 and max(n[k:k + 2]) <= max(n[k - 3:k]) and k - last > 5:
                at_desk = [x['state']['cashier_at_desk'] for x in st if k <= x['t'] <= k + 3]
                if at_desk and sum(at_desk) / len(at_desk) >= 0.5:
                    out.append({'video': vid, 't': float(k), 'n': n[k - 3:k + 3], 's': s[k - 3:k + 3]}); last = k
    json.dump(out, open(a.out, 'w'), indent=1)
    print(len(out), 'candidates in', len({c['video'] for c in out}), 'videos')


def ask(a):
    import pipeline as P
    from common import chat
    files = {os.path.splitext(os.path.basename(f))[0].replace('Х', 'X'): f for f in glob.glob(os.path.join(a.videos, '*'))}
    cands = json.load(open(a.cand)); res = []
    for c in cands:
        with tempfile.TemporaryDirectory() as tmp:
            ps = []
            for k in range(4):
                fp = os.path.join(tmp, f'{k}.jpg')
                subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-ss', f'{max(0, c["t"] - 1 + k):.2f}', '-i', files[c['video']], '-frames:v', '1', '-q:v', '2', fp])
                if os.path.exists(fp): ps.append(fp)
            t0 = time.time()
            ans, *_ = chat(P.CFG['base_url'], P.CFG['model'], P.ZSYSTEM, LEAVE_Q, ps, LEAVE_SCHEMA, P.CFG['structured'], 768)
        res.append({**c, 'answer': ans, 'latency_s': round(time.time() - t0, 1)})
        print(c['video'], c['t'], ans, flush=True)
    json.dump(res, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['candidates', 'ask'])
    ap.add_argument('--det'); ap.add_argument('--zoom'); ap.add_argument('--states'); ap.add_argument('--videos'); ap.add_argument('--cand'); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    candidates(a) if a.mode == 'candidates' else ask(a)
