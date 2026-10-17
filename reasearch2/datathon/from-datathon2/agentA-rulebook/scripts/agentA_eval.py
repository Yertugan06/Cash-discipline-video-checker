"""Batch runner for the shared validation scorer.

Stage `full` runs the complete service pipeline (decode, perception, events, rules,
evidence) per unique clip and records end-to-end runtime; perception is cached.
Stage `rules` replays cached perception through events + rules only (for tuning).
Both write `preds/A_<variant>.json` in the scorer format. Prints aggregates only.
"""

import argparse
import hashlib
import json
import secrets
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.codex import load_codex  # noqa: E402
from backend.config import Settings  # noqa: E402

GT_DIR = next(
    p
    for p in (
        Path.home() / "dt26-validation/validation-private",
        Path.home() / "dt26-validation/data/validation-private",
    )
    if (p / "gt.json").is_file()
)
RUN_DIR = ROOT / "runtime/agentA_runs"
INDEX = ROOT / "runtime/agentA_index.json"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def settings(device: str) -> Settings:
    return Settings(
        api_key=secrets.token_urlsafe(16),
        work_dir=ROOT / "runtime",
        cache_dir=ROOT / "cache",
        device=device,
        reuse_perception=True,
    )


def clip_ids(split: str, only: list[str]) -> list[str]:
    gt = json.loads((GT_DIR / "gt.json").read_text())
    groups = json.loads((GT_DIR / "split.json").read_text())
    ids = [k for k in gt if split == "all" or groups[k] == split]
    return [k for k in ids if not only or k in only]


def run_full(ids: list[str], config: Settings) -> None:
    from backend.pipeline import analyze_video

    gt = json.loads((GT_DIR / "gt.json").read_text())
    index = json.loads(INDEX.read_text()) if INDEX.is_file() else {}
    for clip in ids:
        path = Path(gt[clip]["path"])
        out = RUN_DIR / clip
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        started = time.perf_counter()
        record = {"error": None}
        try:
            result = analyze_video(path, out, config)
            record.update(
                duration=result.video.duration_sec,
                cached=result.perception_cached,
                findings=[
                    {"rule_id": v.rule_id, "t": v.timecode_sec, "conf": v.confidence}
                    for v in result.violations
                ],
            )
        except Exception as exc:  # recorded as an error, never a clean verdict
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
        record["runtime_s"] = time.perf_counter() - started
        record["checksum"] = sha256(path)
        index[clip] = record
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(json.dumps(index, indent=1))
        print(f"{clip}: runtime {record['runtime_s']:.1f}s error={bool(record['error'])}", flush=True)


def replay(ids: list[str], config: Settings) -> dict[str, dict]:
    from backend.events import build_events
    from backend.perception import perceive_video
    from backend.rules import Context, evaluate_rules

    codex = load_codex(config.codex_path)
    index = json.loads(INDEX.read_text())
    output = {}
    for clip in ids:
        record = index.get(clip)
        if not record or record.get("error"):
            output[clip] = {"error": (record or {}).get("error", "not perceived"), "findings": []}
            continue
        scene, observations, perception = perceive_video(
            [], record["checksum"], config, time.perf_counter() + 600
        )
        if not perception.get("cache_hit"):
            raise RuntimeError(f"{clip}: perception cache is stale; rerun --stage full")
        log = build_events(scene, observations, perception, config.sample_fps, record["duration"])
        ctx = Context(codex, log, observations, scene, record["duration"])
        ctx.extras_path = perception.get("extras_path")
        findings = evaluate_rules(ctx)
        output[clip] = {
            "error": None,
            "findings": [
                {"rule_id": f.rule_id, "t": f.timestamp_sec, "conf": f.confidence}
                for f in findings
            ],
        }
    return output


def write_preds(variant: str, ids: list[str], findings: dict[str, dict]) -> Path:
    from backend.rules import RULE_PRIORITY, scorer_code

    index = json.loads(INDEX.read_text())
    preds = {}
    for clip in ids:
        record = index.get(clip, {})
        items = findings[clip]["findings"]
        items = sorted(items, key=lambda f: (RULE_PRIORITY.get(f["rule_id"], 99), f["t"]))
        preds[clip] = {
            "verdict": "violation" if items else "no_violation",
            "events": [
                {"t": round(f["t"], 2), "code": scorer_code(f["rule_id"]), "conf": f["conf"],
                 "rule": f["rule_id"]}
                for f in items
            ],
            "runtime_s": record.get("runtime_s"),
            "error": findings[clip]["error"],
        }
    path = ROOT / "preds" / f"A_{variant}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preds, indent=1, ensure_ascii=False))
    score_root = ROOT / "score_root/data/validation-private"
    (score_root / "preds").mkdir(parents=True, exist_ok=True)
    for name in ("gt.json", "split.json"):
        shutil.copy(GT_DIR / name, score_root / name)
    shutil.copy(path, score_root / "preds" / path.name)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["full", "rules"], required=True)
    parser.add_argument("--split", choices=["dev", "lockbox", "all"], default="dev")
    parser.add_argument("--variant", required=True)
    parser.add_argument("--clips", nargs="*", default=[])
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    ids = clip_ids(args.split, args.clips)
    config = settings(args.device)
    if args.stage == "full":
        run_full(ids, config)
    findings = replay(ids, config)
    print("wrote", write_preds(args.variant, ids, findings))


if __name__ == "__main__":
    main()
