"""Нормализация видео и нарезка кадров через ffmpeg (любой кодек/поворот/разрешение).

Все кадры:      python scripts/extract_frames.py --videos /data/videos --out work/frames --fps 2
Только золото:  python scripts/extract_frames.py --videos /data/videos --out work/gold_frames --gold data/gold_states.csv
"""
import argparse, csv, glob, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import video_id

EXT = ('.mov', '.mp4', '.avi', '.mkv', '.m4v', '.webm')


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=codec_name,width,height,avg_frame_rate:stream_side_data=rotation:format=duration',
                          '-of', 'json', path], capture_output=True, text=True).stdout
    try:
        d = json.loads(out); s = d['streams'][0]
        rot = next((sd.get('rotation') for sd in s.get('side_data_list', []) if 'rotation' in sd), 0)
        return {'codec': s.get('codec_name'), 'width': s.get('width'), 'height': s.get('height'),
                'fps': s.get('avg_frame_rate'), 'rotation': rot, 'duration': float(d['format']['duration'])}
    except Exception:
        return {}


def all_frames(path, out_root, fps, height):
    vid = video_id(path); d = os.path.join(out_root, vid); os.makedirs(d, exist_ok=True)
    vf = f'fps={fps}' + (f',scale=-2:{height}' if height else '')      # автоповорот ffmpeg применяет сам
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', vf, '-q:v', '2', os.path.join(d, '%06d.jpg')], check=True)
    files = sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
    meta = {'video': vid, 'source': os.path.abspath(path), 'fps': fps, 'probe': probe(path),
            'frames': [{'t': round(i / fps, 3), 'path': os.path.join(d, f)} for i, f in enumerate(files)]}
    json.dump(meta, open(os.path.join(d, 'frames.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return vid, len(files)


def gold_frames(paths, out_root, gold_csv, height):
    by_vid = {video_id(p): p for p in paths}
    rows = list(csv.DictReader(open(gold_csv, encoding='utf-8'), delimiter=';'))
    need = sorted({(r['video'], float(r['t'])) for r in rows})
    os.makedirs(out_root, exist_ok=True); items = []
    for vid, t in need:
        if vid not in by_vid:
            print('нет файла для', vid); continue
        p = os.path.join(out_root, f'{vid}_{t:07.2f}.jpg')
        vf = ['-vf', f'scale=-2:{height}'] if height else []
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', by_vid[vid], '-frames:v', '1', *vf, '-q:v', '2', p], check=True)
        items.append({'video': vid, 't': t, 'path': p})
    json.dump({'frames': items}, open(os.path.join(out_root, 'gold_frames.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return len(items)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', nargs='+', required=True, help='папка(и) или файлы видео')
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=float, default=2.0)
    ap.add_argument('--height', type=int, default=848, help='0 = не масштабировать')
    ap.add_argument('--gold', help='gold_states.csv → вырезать только эти кадры')
    ap.add_argument('--skip-duplicates', default='X-47,X-48', help='не обрабатывать побайтные копии')
    a = ap.parse_args()
    paths = []
    for v in a.videos:
        paths += sorted(glob.glob(os.path.join(v, '*'))) if os.path.isdir(v) else [v]
    paths = [p for p in paths if p.lower().endswith(EXT) and video_id(p) not in a.skip_duplicates.split(',')]
    if a.gold:
        print('gold frames:', gold_frames(paths, a.out, a.gold, a.height))
    else:
        with ThreadPoolExecutor(4) as ex:
            for vid, n in ex.map(lambda p: all_frames(p, a.out, a.fps, a.height), paths):
                print(vid, n, 'frames')
