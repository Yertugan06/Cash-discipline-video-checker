"""Start the candidate's complete single-VM checker and realtime gateway."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checker-python", type=Path, required=True)
    parser.add_argument("--gateway-python", type=Path, required=True)
    parser.add_argument("--model-python", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--visual-checks", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    root = args.root.resolve()
    runtime = root / "runtime"
    state_dir = runtime / "realtime"
    state_dir.mkdir(parents=True, exist_ok=True)
    key_file = runtime / "service-key"
    if not key_file.exists():
        key_file.write_text(secrets.token_urlsafe(32))
        key_file.chmod(0o600)
    env = {
        **os.environ,
        "PYTHONPATH": str(root),
        "API_KEY": key_file.read_text().strip(),
        "DETECTOR": "f1",
        "RULE_SCOPE": "detector",
        "DEVICE": "cuda",
        "CPU_THREADS": "2",
        "OMP_NUM_THREADS": "2",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "WORK_DIR": str(runtime),
        "CACHE_DIR": str(runtime / "perception_cache"),
        "WEIGHTS_DIR": str(args.weights),
        "F1_VISUAL_CHECKS": "1" if args.visual_checks else "0",
        "F1_VISUAL_FAMILIES": "safe",
        "F1_VISUAL_MODEL_PATH": str(args.model),
        "F1_VISUAL_WORKER_PYTHON": str(args.model_python),
        "F1_VISUAL_CACHE_DIR": str(runtime / "visual_answer_cache"),
        "F1_VISUAL_BUDGET_S": "90",
        "F1_VISUAL_REQUEST_TIMEOUT_S": "45",
        "CHECKER_URL": "http://127.0.0.1:8003",
        "VIDEO_DIR": str(args.videos),
        "LABELS": str(root / "data/prepared/videos.jsonl"),
        "STATE_FILE": str(state_dir / "state.live.json"),
    }
    result = {}
    for name, python, target, port in (
        ("checker", args.checker_python, "backend.main:create_app", 8003),
        ("gateway", args.gateway_python, "realtime.gateway:create_app", 8103),
    ):
        with socket.socket() as check:
            busy = check.connect_ex(("127.0.0.1", port)) == 0
        if busy:
            result[name] = {"port": port, "status": "already listening; not replaced"}
            continue
        with (runtime / (name + ".log")).open("ab") as output:
            process = subprocess.Popen(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "--factory",
                    target,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=root,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        (runtime / (name + ".pid")).write_text(str(process.pid))
        result[name] = {"pid": process.pid, "port": port, "status": "started; health check pending"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
