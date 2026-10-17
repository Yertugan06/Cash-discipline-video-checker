"""Можно ли на ноутбуке (6 ГБ) звать 8B только на окна действий: время загрузки 8B, окна по 4 кадра, возврат к 4B.

  python prototype/tools/time_8b_local.py --videos open/open/videos
"""
import argparse, glob, json, os, subprocess, sys, tempfile, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DETECTOR', '0')
import pipeline as P                                   # noqa: E402
from common import chat                                # noqa: E402
from tools.action_windows import SCHEMA, Q             # noqa: E402

WINDOWS = [('X-34', 12), ('X-44', 16), ('X-45', 16)]


def frames(video, t0, tmp):
    ps = []
    for k in range(4):
        p = os.path.join(tmp, f'{t0}_{k}.jpg')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-ss', f'{t0 + k:.2f}', '-i', video, '-frames:v', '1', '-q:v', '2', p])
        ps.append(p)
    return ps


def ps_info():
    d = json.loads(urllib.request.urlopen('http://127.0.0.1:11434/api/ps', timeout=10).read())
    return [(m['name'], round(m.get('size', 0) / 2**30, 2), round(m.get('size_vram', 0) / 2**30, 2)) for m in d.get('models', [])]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--videos', required=True); a = ap.parse_args()
    files = {os.path.splitext(os.path.basename(f))[0].replace('Х', 'X'): f for f in glob.glob(os.path.join(a.videos, '*'))}
    with tempfile.TemporaryDirectory() as tmp:
        for i, (vid, t0) in enumerate(WINDOWS):
            ps = frames(files[vid], t0, tmp)
            t = time.time()
            ans, *_ = chat(P.CFG['base_url'], 'qwen3-vl:8b-instruct', P.ZSYSTEM, Q, ps, SCHEMA, 'ollama', 768)
            print(f"8B {'(с загрузкой) ' if i == 0 else ''}{vid}@{t0}: {time.time() - t:.1f} s  {ans}", flush=True)
        print('загружено:', ps_info(), '(имя, всего ГБ, на GPU ГБ)', flush=True)
        f0 = frames(files['X-34'], 5, tmp)[0]
        t = time.time(); r = P.ask({'t': 5.0, 'path': f0})
        print(f"4B анкета после 8B (с перезагрузкой 4B): {time.time() - t:.1f} s ok={r['ok']}", flush=True)
        t = time.time(); r = P.ask({'t': 5.0, 'path': f0})
        print(f"4B анкета, модель уже в памяти: {time.time() - t:.1f} s", flush=True)
        print('загружено:', ps_info(), flush=True)


if __name__ == '__main__':
    main()
