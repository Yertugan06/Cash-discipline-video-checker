"""Шаг проверки: VLM отвечает да/нет на вопрос правила по 3 кадрам вокруг таймкода. Срезает ложные срабатывания.

python scripts/verify_candidates.py --violations runs/q35_9b/violations --frames work/frames --model Qwen/Qwen3.5-9B
→ дописывает в каждое нарушение поля verified (yes/no/unclear) и verify_evidence.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import chat, load_prompt, load_json

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['answer', 'evidence'],
          'properties': {'answer': {'type': 'string', 'enum': ['yes', 'no', 'unclear']}, 'evidence': {'type': 'string'}}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--violations', required=True); ap.add_argument('--frames', required=True)
    ap.add_argument('--model', required=True); ap.add_argument('--base-url', default='http://localhost:8000/v1')
    ap.add_argument('--max-side', type=int, default=1024); ap.add_argument('--structured', default='json_schema')
    a = ap.parse_args()
    system = load_prompt('system.txt'); tpl = load_prompt('verify.txt')
    for p in sorted(glob.glob(os.path.join(a.violations, '*.json'))):
        d = load_json(p)
        if not d['violations']: continue
        frames = load_json(os.path.join(a.frames, d['video'], 'frames.json'))['frames']
        for v in d['violations']:
            pics = [min(frames, key=lambda f: abs(f['t'] - t)) for t in v['evidence_t']]
            q = tpl.format(n=len(pics), times=', '.join(f"{f['t']:.1f}" for f in pics), question=v['verify_question'])
            ans, raw, lat, err = chat(a.base_url, a.model, system, q, [f['path'] for f in pics], SCHEMA, a.structured, a.max_side)
            v['verified'] = (ans or {}).get('answer', 'unclear'); v['verify_evidence'] = (ans or {}).get('evidence', err or '')
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(d['video'], [(v['rule'], v['verified']) for v in d['violations']])


if __name__ == '__main__':
    main()
