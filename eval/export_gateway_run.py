"""Export a saved realtime-gateway run (`~/realtime-state/state.<run>.json`) as a directory of API
job results, the input of `eval.run_eval` and `eval.check_outputs`.

Per clip it writes `<clip>.json` (the checker's `DoneJob` verbatim, or a `FailedJob` with the
gateway's error) and `<clip>.meta.json` with `wall_s`, upload start to result as the gateway
measured it. Writes no label: the gateway's `label` field is dropped. A run with a clip still
queued or processing is refused, so a partial run is never scored as a complete one.

    .venv/bin/python -m eval.export_gateway_run <state.json> <out_dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.clip_id import parse_clip_id


def export(items: list[dict], out_dir: Path) -> int:
    """Write one result and one meta file per item; returns the number of clips written."""
    pending = [i["name"] for i in items if i["status"] not in ("done", "failed")]
    if pending:
        raise ValueError(f"run is not finished, still pending: {', '.join(pending)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for item in items:
        clip = parse_clip_id(Path(item["name"]).stem)
        if clip in seen:
            raise ValueError(f"two items for {clip} in the run")
        seen.add(clip)
        if item["status"] == "done":
            result = item["result"]
        else:
            result = {
                "job_id": item.get("job_id") or "",
                "status": "failed",
                "error": item["error"],
            }
        (out_dir / f"{clip}.json").write_text(json.dumps(result), encoding="utf-8")
        wall_s = round(item["finished_at"] - item["started_at"], 1)
        (out_dir / f"{clip}.meta.json").write_text(json.dumps({"wall_s": wall_s}), encoding="utf-8")
    return len(seen)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("state", type=Path)
    ap.add_argument("out_dir", type=Path)
    args = ap.parse_args(argv)
    items = json.loads(args.state.read_text(encoding="utf-8"))
    print(f"wrote {export(items, args.out_dir)} clips to {args.out_dir}")


if __name__ == "__main__":
    main()
