"""Start only the pinned checker; preserve the existing gateway and annotations."""

import argparse
import json
import os
import secrets
import socket
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ("root", "python", "model-python", "weights", "model"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    runtime = root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    key = runtime / "service-key"
    if not key.exists():
        key.write_text(secrets.token_urlsafe(32))
        key.chmod(0o600)
    with socket.socket() as check:
        if check.connect_ex(("127.0.0.1", 8003)) == 0:
            raise RuntimeError("Checker port is already occupied; no process was replaced")
    env = {
        **os.environ, "PYTHONPATH": str(root), "API_KEY": key.read_text().strip(),
        "DETECTOR": "f1", "RULE_SCOPE": "detector", "DEVICE": "cuda", "CPU_THREADS": "2",
        "OMP_NUM_THREADS": "2", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "WORK_DIR": str(runtime), "CACHE_DIR": str(runtime / "perception_cache"),
        "WEIGHTS_DIR": str(args.weights), "OVERRIDES_PATH": str(root / "config/overrides.yaml"),
        "F1_VISUAL_CHECKS": "1", "F1_VISUAL_FAMILIES": "safe",
        "F1_VISUAL_MODEL_PATH": str(args.model),
        "F1_VISUAL_WORKER_PYTHON": str(args.model_python),
        "F1_VISUAL_CACHE_DIR": str(runtime / "visual_answer_cache"),
        "F1_VISUAL_BUDGET_S": "90", "F1_VISUAL_REQUEST_TIMEOUT_S": "45",
    }
    with (runtime / "a23-checker.log").open("ab") as log:
        process = subprocess.Popen(
            [str(args.python), "-m", "uvicorn", "--factory", "backend.main:create_app",
             "--host", "127.0.0.1", "--port", "8003"], cwd=root, env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    (runtime / "checker.pid").write_text(str(process.pid))
    result = {"pid": process.pid, "port": 8003, "source_root": str(root),
              "visual_checks": "Qwen3-VL-4B safe only", "camera": "automatic; no manual ROI",
              "status": "started; readiness pending"}
    (runtime / "a23-checker-start.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
