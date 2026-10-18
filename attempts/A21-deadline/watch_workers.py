"""Stream worker state changes over one persistent SSH connection per VM."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
from pathlib import Path

REMOTE = r'''
import hashlib,json,time
from pathlib import Path
h=Path.home(); b=h/'workspaces/datathon26-workers'
d2=(b/'runs/worker-1/a21-recognition-0246').exists()
host='datathon2' if d2 else 'datathon3'
jobs=[(1,'a21-recognition-0246'),(2,'a21-visual-checks-0246')] if d2 else [(1,'a21-evidence-0246'),(2,'a21-validation-0246')]
previous=None; heartbeat=0
while True:
    records=[]
    for slot,task in jobs:
        root=b/'runs'/('worker-'+str(slot))/task
        workspace=b/('worker-'+str(slot))/'attempts/A21-deadline'
        try:
            record={'slot':slot,'task':task,'state':(root/'status').read_text().strip()}
            record['progress']=[{'path':str(p),'text':p.read_text()[-5000:]} for p in workspace.glob('progress*.md')]
            record['result']=(root/'result.md').read_text()[-6000:] if (root/'result.md').exists() else None
            records.append(record)
        except OSError as exc:
            records.append({'slot':slot,'task':task,'error':str(exc)})
    digest=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
    now=time.monotonic()
    if digest!=previous or now-heartbeat>=30:
        print(json.dumps({'host':host,'changed':digest!=previous,'workers':records}),flush=True)
        previous=digest; heartbeat=now
    time.sleep(5)
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    guard = threading.Lock()
    processes: list[subprocess.Popen] = []

    def watch(host: str) -> None:
        command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-o", "ServerAliveInterval=30", host, "python3", "-u", "-"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        processes.append(process)
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(REMOTE)
        process.stdin.close()
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"host": host, "monitor_message": line.strip()}
            with guard:
                if "workers" in event:
                    temporary = args.out / (host + ".partial")
                    temporary.write_text(json.dumps(event, indent=2) + "\n")
                    temporary.replace(args.out / (host + ".json"))
                with (args.out / "events.jsonl").open("a") as output:
                    output.write(json.dumps(event) + "\n")
                if event.get("changed"):
                    print(json.dumps({"host": host, "states": {r["task"]: r.get("state", "error") for r in event["workers"]}}), flush=True)
        code = process.wait()
        print(json.dumps({"host": host, "monitor_disconnected": True, "exit_code": code}), flush=True)

    threads = [threading.Thread(target=watch, args=(host,), daemon=True) for host in ("datathon2", "datathon3")]
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
