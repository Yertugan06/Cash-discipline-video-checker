"""Local VLM harness (Qwen3-VL or Qwen2.5-VL, transformers). All inference local; raw model text stays private.

Frames are decoded with PyAV at a uniform rate using container PTS (clips are VFR) and resized to the model's
patch grid: multiples of 32 for Qwen3-VL (16 px patch x 2x2 merge), 28 for Qwen2.5-VL (14 px x 2x2).
Qwen3-VL gets frame metadata so its timestamp tokens equal real seconds from the window start;
Qwen2.5-VL gets the sampling fps for its absolute-time position ids. Window offset is added back after parsing.
Model directory: env VLM_DIR (family read from its config.json).

Library use:  run_jobs(model, processor, jobs, prompt) -> list of {clip, t0, t1, text, timing...}
CLI smoke:    python -I vlm.py smoke <repo_root> <clip_id> <fps> <short_side>
"""
import json, os, re, sys, time

os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1'); os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
import av
import numpy as np
import torch

MODEL_DIR = os.environ.get('VLM_DIR', '/home/yertugan/models/Qwen3-VL-4B-Instruct')
FAMILY = json.load(open(os.path.join(MODEL_DIR, 'config.json')))['model_type']  # 'qwen3_vl' | 'qwen2_5_vl'
MULT = 28 if FAMILY == 'qwen2_5_vl' else 32


def load():
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration, Qwen3VLForConditionalGeneration
    cls = Qwen2_5_VLForConditionalGeneration if FAMILY == 'qwen2_5_vl' else Qwen3VLForConditionalGeneration
    quant = os.environ.get('VLM_QUANT', 'none')  # none | int8 | nf4 (bitsandbytes; for a GPU shared with other jobs)
    kw = {}
    if quant != 'none':
        from transformers import BitsAndBytesConfig
        kw['quantization_config'] = (BitsAndBytesConfig(load_in_8bit=True, llm_int8_skip_modules=['visual', 'lm_head'])
                                     if quant == 'int8' else
                                     BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                                        bnb_4bit_compute_dtype=torch.bfloat16,
                                                        llm_int8_skip_modules=['visual', 'lm_head']))
    t0 = time.time()
    model = cls.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map='cuda', attn_implementation='sdpa', low_cpu_mem_usage=True, **kw)
    model.eval()
    proc = AutoProcessor.from_pretrained(MODEL_DIR)
    return model, proc, time.time() - t0


def frames(path, fps, short_side, t0=0.0, t1=None):
    """Uniform PTS sampling in [t0, t1). Returns uint8 (T,3,H,W) with even T, and sample times."""
    out, ts = [], []
    with av.open(path) as c:
        s = c.streams.video[0]; s.thread_type = 'AUTO'
        if t0 > 1:
            c.seek(int(max(0, t0 - 1) / s.time_base), stream=s, backward=True)
        nxt = t0
        for f in c.decode(s):
            t = float(f.pts * s.time_base)
            if t1 is not None and t >= t1:
                break
            if t + 1e-6 < nxt:
                continue
            nxt += 1.0 / fps
            while nxt <= t:
                nxt += 1.0 / fps
            img = f.to_image()
            w, h = img.size
            sc = short_side / min(w, h)
            W, H = max(MULT, round(w * sc / MULT) * MULT), max(MULT, round(h * sc / MULT) * MULT)
            out.append(np.asarray(img.resize((W, H)), dtype=np.uint8).transpose(2, 0, 1)); ts.append(t)
    if len(out) % 2:
        out.append(out[-1]); ts.append(ts[-1] + 1.0 / fps)
    return torch.from_numpy(np.stack(out)), ts


@torch.inference_mode()
def generate(model, proc, video, fps, prompt, max_new_tokens=400):
    msgs = [{'role': 'user', 'content': [{'type': 'video'}, {'type': 'text', 'text': prompt}]}]
    text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    if FAMILY == 'qwen2_5_vl':
        inputs = proc(text=[text], videos=[video], fps=[fps], do_resize=False, return_tensors='pt').to(model.device)
    else:
        meta = {'fps': fps, 'frames_indices': list(range(len(video))), 'total_num_frames': len(video),
                'duration': len(video) / fps}
        inputs = proc(text=[text], videos=[video], video_metadata=[meta], do_sample_frames=False, do_resize=False,
                      cap_pixels_per_frame=False, return_tensors='pt').to(model.device)
    n_in = inputs['input_ids'].shape[1]
    torch.cuda.synchronize(); t0 = time.time()
    out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    torch.cuda.synchronize()
    ans = proc.batch_decode(out[:, n_in:], skip_special_tokens=True)[0]
    return ans, {'gen_s': time.time() - t0, 'in_tokens': n_in, 'out_tokens': out.shape[1] - n_in}


def run_jobs(model, proc, jobs, prompt_fn, log=None):
    """jobs: dicts with clip, path, t0, t1 (None=end), fps, short_side. prompt_fn(job)->str."""
    res = []
    for j in jobs:
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            vid, ts = frames(j['path'], j['fps'], j['short_side'], j.get('t0', 0.0), j.get('t1'))
            dec = time.time() - t0
            ans, st = generate(model, proc, vid, j['fps'], prompt_fn(j))
            r = dict(j, text=ans, decode_s=dec, n_frames=len(vid), frame_hw=list(vid.shape[2:]),
                     peak_gb=torch.cuda.max_memory_allocated() / 2**30, total_s=time.time() - t0, error=None, **st)
        except Exception as e:  # recorded explicitly, never silently dropped
            torch.cuda.empty_cache()
            r = dict(j, text=None, error=f'{type(e).__name__}: {e}'[:300], total_s=time.time() - t0)
        res.append(r)
        if log:
            with open(log, 'a') as f:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return res


def parse_events(text):
    """Extract a JSON object/list with events from model text. Returns (events, ok)."""
    if not text:
        return [], False
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    body = m.group(1) if m else text
    for cand in (body, body[body.find('{'):body.rfind('}') + 1], body[body.find('['):body.rfind(']') + 1]):
        try:
            d = json.loads(cand)
        except Exception:
            continue
        ev = d.get('events', d.get('violations', [])) if isinstance(d, dict) else d
        return [e for e in ev if isinstance(e, dict)], True
    return [], False


def to_sec(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v)
    m = re.match(r'\s*(\d+):(\d+(?:\.\d+)?)', s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r'\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else None


if __name__ == '__main__' and sys.argv[1] == 'smoke':
    root, clip, fps, side = sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])
    gt = json.load(open(os.path.join(root, 'data', 'validation-private', 'gt.json')))
    model, proc, load_s = load()
    print(f'load {load_s:.1f}s | vram after load {torch.cuda.memory_allocated() / 2**30:.2f} GB')
    r = run_jobs(model, proc, [{'clip': clip, 'path': gt[clip]['path'], 'fps': fps, 'short_side': side}],
                 lambda j: 'List, in order with timestamps, what the people in this video do with their hands. Reply in at most 5 short lines.')[0]
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k not in ('text', 'path')})
    print('answer chars:', len(r['text'] or ''), '| contains timestamps:', bool(re.search(r'\d+(\.\d+)?\s*s', r['text'] or '')))
