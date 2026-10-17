"""Profile prefill vs decode and peak VRAM for several frame budgets on one clip (timing only, no text printed).
Usage: python -I vlm_profile.py <repo_root> <clip_id> <fps:side:t1> [...]   (t1 = seconds of clip to use, 0 = all)
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch  # noqa: E402
import vlm  # noqa: E402

root, clip = sys.argv[1], sys.argv[2]
gt = json.load(open(os.path.join(root, 'validation-private', 'gt.json')))
model, proc, load_s = vlm.load()
print(f'load {load_s:.1f}s | vram after load {torch.cuda.memory_allocated() / 2**30:.2f} GB | '
      f'free/total {[round(x / 2**30, 2) for x in torch.cuda.mem_get_info()]}', flush=True)
for spec in sys.argv[3:]:
    fps, side, t1 = spec.split(':'); fps, side, t1 = float(fps), int(side), float(t1) or None
    vid, ts = vlm.frames(gt[clip]['path'], fps, side, 0.0, t1)
    for new in (1, 64):
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        try:
            _, st = vlm.generate(model, proc, vid, fps, 'Describe the video.', max_new_tokens=new)
            print(f'{spec}: frames {len(vid)} hw {list(vid.shape[2:])} in_tokens {st["in_tokens"]} new {st["out_tokens"]} '
                  f'gen {st["gen_s"]:.1f}s peak {torch.cuda.max_memory_allocated() / 2**30:.2f} GB', flush=True)
        except Exception as e:
            print(f'{spec}: ERROR {type(e).__name__}: {str(e)[:120]}', flush=True)
