"""Run every clip in a folder through a checker API and print one replay-style JSON line each.

    python api_run.py http://127.0.0.1:8001 <api key file> /videos [<dump dir>] > api.jsonl

The lines carry sha256 + findings ({rule_id, t}) so `scripts/replay_f1.py score` can score
them like a replay, plus runtime, evidence-frame count and status. With a dump dir, every API
result is also saved as `<clip>.json` plus `<clip>.meta.json` ({"wall_s"}), the layout
`eval/check_outputs.py` reads.
"""

import hashlib
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

base, key_file, folder = sys.argv[1], sys.argv[2], Path(sys.argv[3])
dump = Path(sys.argv[4]) if len(sys.argv) > 4 else None
key = Path(key_file).read_text().strip()


def call(method: str, path: str, body: bytes | None = None, ctype: str | None = None) -> dict:
    request = urllib.request.Request(base + path, data=body, method=method)
    request.add_header("X-API-Key", key)
    if ctype:
        request.add_header("Content-Type", ctype)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


for video in sorted(folder.iterdir()):
    data = video.read_bytes()
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{video.name}"\r\n'
            f"Content-Type: video/quicktime\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    started = time.monotonic()
    job = call("POST", "/api/v1/analyze", body, f"multipart/form-data; boundary={boundary}")
    while True:
        result = call("GET", f"/api/v1/jobs/{job['job_id']}")
        if result["status"] != "processing":
            break
        time.sleep(1)
    wall = round(time.monotonic() - started, 1)
    if dump:
        dump.mkdir(parents=True, exist_ok=True)
        (dump / f"{video.stem}.json").write_text(json.dumps(result, ensure_ascii=False))
        (dump / f"{video.stem}.meta.json").write_text(json.dumps({"wall_s": wall}))
    row = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "name": video.name,
        "status": result["status"],
        "runtime_s": wall,
    }
    if result["status"] == "done":
        row["verdict"] = result["verdict"]
        row["findings"] = [
            {"rule_id": v.get("rule_id") or v["type"], "t": v["timecode_sec"]}
            for v in result["violations"]
        ]
        row["evidence_frames"] = sum(len(v["evidence_frames"]) for v in result["violations"])
    else:
        row["findings"] = []
        row["error"] = result.get("error")
    print(json.dumps(row), flush=True)
