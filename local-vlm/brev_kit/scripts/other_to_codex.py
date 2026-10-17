"""Открытый мир: записи «other» из анкеты → поиск похожих норм в кодексе → VLM выбирает ID нормы или NONE.
Норма не генерируется: выбирается из списка кандидатов.

python scripts/other_to_codex.py --violations runs/q35_9b/violations --frames work/frames --model Qwen/Qwen3.5-9B \
       --embedder BAAI/bge-m3            # без --embedder — простое пересечение слов
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import chat, load_prompt, load_json, load_codex

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['rule_id', 'evidence'],
          'properties': {'rule_id': {'type': 'string'}, 'evidence': {'type': 'string'}}}


class Retriever:
    def __init__(self, rows, model_name=None):
        self.rows = rows
        self.texts = [f"{r['rule']} {r['breach_visual']}" for r in rows]
        self.model = None
        if model_name:
            from sentence_transformers import SentenceTransformer       # веса скачать заранее, в рантайме сети нет
            self.model = SentenceTransformer(model_name)
            self.emb = self.model.encode(self.texts, normalize_embeddings=True)

    def top(self, q, k=5):
        if self.model is not None:
            e = self.model.encode([q], normalize_embeddings=True)[0]
            sc = self.emb @ e
        else:
            w = set(re.findall(r'\w{4,}', q.lower()))
            sc = [len(w & set(re.findall(r'\w{4,}', t.lower()))) for t in self.texts]
        order = sorted(range(len(self.rows)), key=lambda i: -sc[i])[:k]
        return [self.rows[i] for i in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--violations', required=True); ap.add_argument('--frames', required=True)
    ap.add_argument('--model', required=True); ap.add_argument('--base-url', default='http://localhost:8000/v1')
    ap.add_argument('--embedder'); ap.add_argument('--k', type=int, default=5); ap.add_argument('--structured', default='json_schema')
    a = ap.parse_args()
    codex = [r for r in load_codex().values() if r['video_checkable'] in ('yes', 'partial')]
    ret = Retriever(codex, a.embedder); system = load_prompt('system.txt'); tpl = load_prompt('other_to_codex.txt')
    for p in sorted(glob.glob(os.path.join(a.violations, '*.json'))):
        d = load_json(p); frames = load_json(os.path.join(a.frames, d['video'], 'frames.json'))['frames']
        seen = []
        for ob in d.get('observations', []):
            if any(abs(ob['t'] - s) < 5 for s in seen): continue        # одно и то же наблюдение на соседних кадрах
            seen.append(ob['t'])
            cands = ret.top(ob['other'], a.k)
            pics = [min(frames, key=lambda f: abs(f['t'] - t)) for t in (ob['t'] - 1, ob['t'], ob['t'] + 1)]
            q = tpl.format(times=', '.join(f"{f['t']:.1f}" for f in pics), observation=ob['other'],
                           candidates='\n'.join(f"- {c['id']}: {c['breach_visual']}" for c in cands))
            ans, raw, lat, err = chat(a.base_url, a.model, system, q, [f['path'] for f in pics], SCHEMA, a.structured)
            rid = (ans or {}).get('rule_id', 'NONE')
            if rid in {c['id'] for c in cands}:
                c = next(c for c in cands if c['id'] == rid)
                d['violations'].append({'rule': 'open_world', 'type': c['rule'], 'timecode_sec': ob['t'], 'codex_ids': [rid],
                                        'evidence_t': [ob['t'] - 1, ob['t'], ob['t'] + 1], 'description': ob['other'],
                                        'verify_question': c['breach_visual'], 'verify_evidence': ans.get('evidence', ''),
                                        'norm': {'id': rid, 'act': c['act'], 'punkt': c['punkt'], 'quote': c['quote'],
                                                 'url': c['url'], 'strength': c['strength']}})
        d['verdict'] = 'violation' if d['violations'] else 'no_violation'
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(d['video'], 'open-world:', [v['codex_ids'][0] for v in d['violations'] if v['rule'] == 'open_world'])


if __name__ == '__main__':
    main()
