"""Run the local-vlm prototype (branch local-vlm-prototype) on every unique clip; one line per clip
in the replay format ({sha256, findings: [{rule_id, t}]}) so scripts/replay_f1.py score can read it."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "/proto/local-vlm/prototype")
import pipeline as P  # noqa: E402

rows = [json.loads(line) for line in open("/proto/videos.jsonl") if line.strip()]
done = set()
out_path = Path("/out/vlm.jsonl")
if out_path.exists():
    done = {json.loads(line)["sha256"] for line in out_path.read_text().splitlines() if line.strip()}
with out_path.open("a") as out:
    for row in rows:
        if row["sha256"] in done:
            continue
        done.add(row["sha256"])
        video = Path("/videos") / Path(row["path"]).name
        started = time.monotonic()
        try:
            result, debug = P.analyze(str(video), video_name=row["original_id"])
            line = {
                "sha256": row["sha256"], "name": row["original_id"], "verdict": result["verdict"],
                "findings": [{"rule_id": r["rule"], "t": r["timecode_sec"]} for r in debug["rules"]
                             if not r.get("needs_verify")] if result["verdict"] == "violation" else [],
                "all_rules": [{"rule_id": r["rule"], "t": r["timecode_sec"], "needs_verify": r.get("needs_verify")}
                              for r in debug["rules"]],
                "types": [v["type"] for v in result["violations"]],
                "wall_s": round(time.monotonic() - started, 1),
            }
        except Exception as error:  # record and go on; a crash is a result too
            line = {"sha256": row["sha256"], "name": row["original_id"], "findings": [],
                    "error": f"{type(error).__name__}: {error}", "wall_s": round(time.monotonic() - started, 1)}
        out.write(json.dumps(line, ensure_ascii=False) + "\n")
        out.flush()
        print(line["name"], line.get("verdict"), line.get("error", ""), line["wall_s"], flush=True)
