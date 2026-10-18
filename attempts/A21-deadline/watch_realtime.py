"""Wait for one real gateway batch; export numeric verdicts, never evidence images."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=42)
    args = parser.parse_args()
    from backend.clip_id import parse_clip_id

    labels = {
        parse_clip_id(Path(row["path"]).stem): row
        for line in args.labels.read_text().splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    previous = None
    while True:
        items = json.loads(args.state.read_text()) if args.state.exists() else []
        counts = dict(Counter(item["status"] for item in items))
        if counts != previous:
            print(json.dumps({"phase": "gateway", "counts": counts}), flush=True)
            previous = counts
        rows = []
        for item in items:
            if item["status"] not in {"done", "failed"}:
                continue
            result = item.get("result") or {}
            label = labels[parse_clip_id(Path(item["name"]).stem)]
            assert item.get("started_at") is not None and item.get("finished_at") is not None
            rows.append(
                {
                    "sha256": label["sha256"],
                    "name": item["name"],
                    "job_id": item.get("job_id"),
                    "status": item["status"],
                    "runtime_s": round(item["finished_at"] - item["started_at"], 3),
                    "verdict": item.get("verdict"),
                    "findings": [
                        {
                            "rule_id": finding.get("rule_id") or finding["type"],
                            "t": finding["timecode_sec"],
                        }
                        for finding in result.get("violations", [])
                    ],
                    "error": item.get("error"),
                }
            )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.out.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(row) + "\n" for row in rows))
        temporary.replace(args.out)
        if len(items) >= args.expected and len(rows) == len(items):
            assert len({row["name"] for row in rows}) == args.expected
            print(
                json.dumps(
                    {"phase": "complete", "files": len(rows), "failed": counts.get("failed", 0)}
                ),
                flush=True,
            )
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
