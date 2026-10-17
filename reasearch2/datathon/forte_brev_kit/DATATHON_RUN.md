# Run on datathon

The kit is installed in `/home/ubuntu/forte_brev_kit/brev_kit` with its own Python 3.12 `.venv`. Exact package versions are saved in `brev_kit/installed-requirements.txt`.

`videos` links to `/home/ubuntu/data/open/videos`: 42 source videos, 40 unique videos after excluding X-47 and X-48. Preprocessing validated all 40 video manifests and all 32 gold frames (56 labeled field checks).

The model is `Qwen/Qwen3.5-9B`, downloaded into `models/Qwen3.5-9B`. vLLM serves it locally at `http://127.0.0.1:8010/v1` using FP8 weights, a 16,384-token context, and a GPU memory fraction of 0.65. Thinking is disabled for JSON output. Model serving uses offline mode. Existing instance services use their original ports.

The `forte-brev-kit` tmux session runs the gold evaluation followed by the full-video evaluation. The `forte-brev-vlm` tmux session runs the model server. Both sessions survive SSH disconnects.

From a shell on datathon:

```bash
cd ~/forte_brev_kit/brev_kit
cat run_status.txt
tail -f run.log
tail -f server.log
```

Results are written to `runs/q35_9b_fp8_gold/report_states.md` and `runs/q35_9b_fp8/report_videos.md`, with raw model states and violation events beside the reports. The full-video report is produced after the batch completes.

The provided fixture checks passed for cash and unlocked-laptop violations and their clean-video counterparts. Real model responses are checked against the questionnaire schema before proceeding to the next evaluation stage.

This run covers the default gold and full-video stages with Qwen3.5-9B FP8. Candidate verification, embeddings, and comparisons with other models are separate optional runs. Timing measurements reflect shared CPU/GPU use with the instance's existing jobs.

System prerequisites include `ffmpeg` and `build-essential`; Triton's C compiler and CUDA driver check passed after installing the build tools. The initial failed startup log is retained as `brev_kit/server-missing-compiler.log`.

Runner update 20261017T122433Z: installed the supplied Downloads/Telegram Desktop/run_vlm.py exactly (SHA256 `58e489253d27d10cd410b30d7e2a19c5be362cb49cbd009cf4f28ce3ba7d3caa`). Syntax, CLI, mock gold concurrency, and mock full-video output checks passed. The active full-video process keeps its loaded version; its per-video batching matches the updated runner. The updated file is used on subsequent launches. Previous runner: `scripts/run_vlm.py.before-20261017T122433Z`.
