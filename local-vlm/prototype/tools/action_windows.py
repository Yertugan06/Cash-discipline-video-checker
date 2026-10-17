"""Эксперимент: действия кассира по окну из 4 кадров (1 кадр/с) в одном запросе к VLM.
Пары «нарушение / норма» в одни и те же моменты сценария — различает ли модель действие.

  python prototype/tools/action_windows.py --videos open/open/videos --out prototype/work/runs/actions
"""
import argparse, glob, json, os, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline as P                       # noqa: E402
from common import chat                    # noqa: E402
from PIL import Image                      # noqa: E402

CASES = [  # (видео, начало окна, нарушение ли в окне, что ожидаем)
    ('X-34', 10, True, 'клиент ушёл, деньги пересчитывают без него'), ('X-37', 10, False, 'клиент остаётся при пересчёте'),
    ('X-34', 12, True, 'клиент ушёл, деньги пересчитывают без него'), ('X-37', 12, False, 'клиент остаётся при пересчёте'),
    ('X-44', 13, True, 'пересчёт без детектора'), ('X-45', 13, False, 'купюры на детекторе'),
    ('X-44', 16, True, 'пересчёт без детектора'), ('X-45', 16, False, 'купюры на детекторе'),
    ('X-13', 44, True, 'деньги из сумки в сейф без пересчёта'), ('X-14', 33, False, 'пересчитала, потом в сейф'),
    ('X-1', 19, True, 'после машины пересчитала вручную и вернула'), ('X-3', 14, False, 'обычный приём'),
]
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['counting', 'detector_used', 'client_present_start', 'client_present_end', 'cash_goes_to'],
          'properties': {
              'counting': {'type': 'string', 'enum': ['machine', 'by_hand', 'both', 'none']},
              'detector_used': {'type': 'boolean'},
              'client_present_start': {'type': 'boolean'}, 'client_present_end': {'type': 'boolean'},
              'cash_goes_to': {'type': 'string', 'enum': ['safe', 'client', 'drawer_or_desk', 'counting_machine', 'none', 'unclear']}}}
Q = ('These 4 images are consecutive frames, 1 second apart, from an overhead camera at a bank cash desk. Watch what happens across ALL frames:\n'
     '- counting: how the cashier counts banknotes in these seconds: machine (feeds notes into the counting machine), by_hand (flips notes by hand), both, none;\n'
     '- detector_used: the cashier places banknotes on / under the small banknote detector (UV device) at any moment;\n'
     '- client_present_start / client_present_end: a client is at the client side of the desk in the FIRST / in the LAST frame;\n'
     '- cash_goes_to: where the banknotes end up by the last frame.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', required=True); ap.add_argument('--out', required=True); ap.add_argument('--side', type=int, default=768)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = {os.path.splitext(os.path.basename(f))[0].replace('Х', 'X'): f for f in glob.glob(os.path.join(a.videos, '*'))}
    res = []
    for vid, t0, bad, what in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            ps = []
            for k in range(4):
                p = os.path.join(tmp, f'{k}.jpg')
                subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-ss', f'{t0 + k:.2f}', '-i', files[vid], '-frames:v', '1', '-q:v', '2', p])
                if os.path.exists(p): ps.append(p)
            t = time.time()
            ans, raw, lat, err = chat(P.CFG['base_url'], P.CFG['model'], P.ZSYSTEM, Q, ps, SCHEMA, P.CFG['structured'], a.side)
            # лист из 4 кадров для просмотра
            ims = [Image.open(p).convert('RGB') for p in ps]; [im.thumbnail((232, 424)) for im in ims]
            sheet = Image.new('RGB', (sum(im.width for im in ims), ims[0].height), (255, 255, 255)); x = 0
            for im in ims: sheet.paste(im, (x, 0)); x += im.width
            sheet.save(os.path.join(a.out, f'{vid}_{t0}.jpg'), quality=80)
        r = {'video': vid, 't0': t0, 'violation': bad, 'expected': what, 'answer': ans, 'latency_s': round(time.time() - t, 1)}
        res.append(r); print(f"{vid} {t0:>3}s {'НАРУШ' if bad else 'норма'} | {ans} | {r['latency_s']} s", flush=True)
    json.dump(res, open(os.path.join(a.out, 'results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
