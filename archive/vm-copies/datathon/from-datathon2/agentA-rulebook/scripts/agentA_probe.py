"""Feature distributions per label family on cached perception (aggregates only).

Prints, for each feature, the sorted values among clips whose label family matches
the feature's target rule and among clean clips. No clip ids are printed.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from agentA_eval import GT_DIR, INDEX, clip_ids, settings  # noqa: E402

from backend.codex import load_codex  # noqa: E402
from backend.events import build_events  # noqa: E402
from backend.perception import perceive_video  # noqa: E402
from backend.rules import Context  # noqa: E402

# Rule family per labelled clip, from the rulebook table (Untitled.md), not from pixels.
SPEC_FAMILY = {
    "X-1": {"reject"}, "X-2": {"id"}, "X-4": {"cleandesk"}, "X-11": {"pc", "leave"},
    "X-13": {"recount"}, "X-15": {"leave"}, "X-17": {"collector"}, "X-18": {"second"},
    "X-20": {"safe"}, "X-22": {"key"}, "X-24": {"leave"}, "X-26": {"leave"},
    "X-28": {"pc"}, "X-30": {"door", "outsider"}, "X-32": {"door"},
    "X-33": {"door", "outsider"}, "X-34": {"count"}, "X-38": {"cleandesk"},
    "X-40": {"personal"}, "X-44": {"detector"}, "X-46": {"food"},
}


def families() -> dict[str, set[str]]:
    return SPEC_FAMILY


def contexts(split: str):
    config = settings("cpu")
    codex = load_codex(config.codex_path)
    index = json.loads(INDEX.read_text())
    gt = json.loads((GT_DIR / "gt.json").read_text())
    for clip in clip_ids(split, []):
        record = index.get(clip)
        if not record or record.get("error"):
            continue
        scene, observations, perception = perceive_video(
            [], record["checksum"], config, time.perf_counter() + 600
        )
        log = build_events(scene, observations, perception, config.sample_fps, record["duration"])
        ctx = Context(codex, log, observations, scene, record["duration"])
        ctx.extras_path = perception.get("extras_path")
        yield clip, gt[clip], ctx


def report(name: str, values: dict[str, list[float]]) -> None:
    for group, items in values.items():
        shown = " ".join(f"{v:.2f}" for v in sorted(items))
        print(f"{name:28} {group:10} n={len(items):2} [{shown}]")


if __name__ == "__main__":
    import agentA_features as features

    split = sys.argv[1] if len(sys.argv) > 1 else "dev"
    fam = families()
    rows = list(contexts(split))
    for feature in features.FEATURES:
        values: dict[str, list[float]] = {"target": [], "other_viol": [], "clean": []}
        for clip, truth, ctx in rows:
            value = feature.fn(ctx)
            if value is None or not np.isfinite(value):
                continue
            if not truth["violation"]:
                values["clean"].append(value)
            elif feature.family in fam.get(clip, set()):
                values["target"].append(value)
            else:
                values["other_viol"].append(value)
        report(feature.name, values)
