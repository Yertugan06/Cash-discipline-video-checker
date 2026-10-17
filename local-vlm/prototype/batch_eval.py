"""Прогон прототипа по всем видео датасета (как у жюри: по одному видео) + метрики.

  python batch_eval.py --videos ../open/open/videos --out work/runs/proto_4b
  python batch_eval.py --videos ../open/open/videos --out work/runs/proto_4b --only X-26,X-38

Пишет states/*.jsonl (таймлайн — для подбора порогов без GPU), violations/*.json (формат brev_kit) и run_meta.json,
затем запускает brev_kit/scripts/eval_videos.py → report_videos.md. Уже обработанные видео пропускаются (можно прервать и продолжить).
"""
import argparse, csv, glob, json, os, subprocess, sys, time
import pipeline as P


def norm_name(fn):
    return os.path.splitext(os.path.basename(fn))[0].replace('Х', 'X').replace('х', 'X')   # в датасете часть имён с кириллической «Х»


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', required=True); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    a = ap.parse_args()
    files = {norm_name(f): f for f in glob.glob(os.path.join(a.videos, '*')) if f.lower().endswith(('.mov', '.mp4', '.m4v', '.avi', '.mkv', '.webm'))}
    vids = [r['video'] for r in csv.DictReader(open(os.path.join(P.KIT, 'data', 'videos.csv'), encoding='utf-8'), delimiter=';') if not r['duplicate_of']]
    only = set(filter(None, a.only.split(',')))
    if only: vids = [v for v in vids if v in only]
    for d in ('states', 'violations'): os.makedirs(os.path.join(a.out, d), exist_ok=True)
    mp = os.path.join(a.out, 'run_meta.json')
    meta = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {'videos': {}}
    meta.update({'model': P.CFG['model'], 'step': P.CFG['step'], 'max_side': P.CFG['max_side'], 'workers': P.CFG['workers'],
                 'zoom': P.CFG['zoom'], 'prompts': os.path.basename(P.CFG['prompts'])})
    for vid in vids:
        vp = os.path.join(a.out, 'violations', f'{vid}.json')
        if os.path.exists(vp) and not only: continue
        if vid not in files: print(f'{vid}: нет файла'); continue
        res, dbg = P.analyze(files[vid], dump_states=os.path.join(a.out, 'states', f'{vid}.jsonl'),
                             trace_dir=os.path.join(a.out, 'traces', vid), video_name=vid)
        json.dump({'video': vid, 'verdict': res['verdict'], 'violations': dbg['rules']}, open(vp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        meta['videos'][vid] = {'frames': dbg['vlm_calls'], 'ok': dbg['vlm_ok'], 'wall_s': dbg['processing_s'], 'duration_s': dbg['duration_s'],
                               'zoom_checks': dbg['zoom_checks'], 'confirm_calls': dbg['confirm_calls'], 'dropped': dbg['dropped'],
                               'action_calls': dbg.get('action_calls', 0),
                               'mean_latency_s': dbg['mean_latency_s']}
        json.dump(meta, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        found = ', '.join(f"{r['rule']}@{r['timecode_sec']}" + ('?' if r['needs_verify'] else '') for r in dbg['rules']) or '-'
        print(f"{vid}: {res['verdict']:12s} {found:40s} {dbg['processing_s']:6.1f}s / {dbg['duration_s']:.0f}s video, "
              f"vlm {dbg['vlm_calls']} + zoom {dbg['zoom_checks']} + 8B {dbg.get('action_calls', 0)}"
              + (f" dropped {','.join(dbg['dropped'])}" if dbg['dropped'] else ''), flush=True)
    subprocess.run([sys.executable, '-I', os.path.join(P.KIT, 'scripts', 'eval_videos.py'), '--violations', os.path.join(a.out, 'violations'),
                    '--run-meta', mp, '--out', os.path.join(a.out, 'report_videos.md')], stdout=subprocess.DEVNULL)
    print('report:', os.path.join(a.out, 'report_videos.md'))


if __name__ == '__main__':
    main()
