"""Numeric A26 replay; read shared base/cache/traces, write only this attempt."""

import argparse
import contextlib
import difflib
import hashlib
import importlib.util
import io
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

CANDIDATE = """def a_outsider_zone(ctx: Context) -> list[Finding]:
    if not ctx.log.coverage.get("roles"):
        return []
    distinct_seen = {}
    for observation in ctx.observations:
        people = [p for p in observation.detections if p.label == "person" and p.role != "glass"]
        cashier_ids = {p.track_id for p in people if p.role == "cashier" and p.track_id}
        if cashier_ids:
            for person in people:
                if person.track_id and person.track_id not in cashier_ids:
                    distinct_seen.setdefault(person.track_id, observation.timestamp_sec)
    # A new track in the zone may be the lost cashier; location cannot establish identity.
    return [
        finding
        for finding in sustained(ctx, "A-OUTSIDER-ZONE", "PERSON_IN_CASHIER_ZONE")
        if distinct_seen.get(str(finding.facts.get("actor_id", "")), float("inf"))
        <= finding.timestamp_sec
    ]
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.base.resolve()))
    import yaml

    from backend.f1 import rules
    from backend.f1.calibration import calibrate
    from backend.f1.codex import load_codex
    from backend.f1.events import EventLog, build_events
    from backend.f1.perception import load_perception_config
    from backend.f1.vision_types import Detection, Event, Observation, Scene

    assert Path(rules.__file__).is_relative_to(args.base.resolve())
    args.out.mkdir(parents=True, exist_ok=True)
    source = Path(rules.__file__)
    text = source.read_text()
    start = text.index("def a_outsider_zone(")
    end = text.index("\ndef a_second_person(", start)
    replacement = CANDIDATE.rstrip() + "\n\n"
    candidate_text = text[:start] + replacement + text[end:]
    (args.out / "candidate.patch").write_text(
        "".join(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                candidate_text.splitlines(keepends=True),
                fromfile="a/backend/f1/rules.py",
                tofile="b/backend/f1/rules.py",
            )
        )
    )
    namespace = vars(rules).copy()
    exec(compile(replacement, "<A26 own candidate>", "exec"), namespace)
    candidate = namespace["a_outsider_zone"]
    spec = importlib.util.spec_from_file_location(
        "a26_existing_replay", args.base / "scripts/replay_f1.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    assert callable(helper.score)
    config = load_perception_config(args.base / "config/perception.yaml")
    codex = load_codex(args.base / "config/f1_codex.yaml")
    enabled = {
        r["rule_id"]
        for r in yaml.safe_load((args.base / "knowledge/rules.yaml").read_text())
        if r.get("enabled")
    }
    labels = [
        json.loads(line)
        for line in (args.base / "data/prepared/videos.jsonl").read_text().splitlines()
        if line.strip()
    ]
    aliases = defaultdict(list)
    expected = {}
    for row in labels:
        aliases[row["sha256"]].append(row["original_id"])
        expected[row["sha256"]] = row["organizer_verdict"] == "violation"
    original = rules.RULES["A-OUTSIDER-ZONE"]

    def evaluate(ctx, modified):
        rules.RULES["A-OUTSIDER-ZONE"] = candidate if modified else original
        try:
            return [asdict(f) for f in rules.evaluate_rules(ctx, enabled)]
        finally:
            rules.RULES["A-OUTSIDER-ZONE"] = original

    rows = []
    for folder in sorted(p for p in args.cache.iterdir() if p.is_dir()):
        path = max(folder.glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        payload = json.loads(path.read_text())
        scene = Scene.model_validate(payload["scene"])
        if scene.candidates:
            scene = calibrate(scene.candidates, args.base / "config/overrides.yaml", folder.name)
        observations = [Observation.model_validate(o) for o in payload["observations"]]
        duration = observations[-1].timestamp_sec + 0.5
        log = build_events(scene, observations, config, 2, duration)
        ctx = rules.Context(codex, log, observations, scene, duration)
        before, after = evaluate(ctx, False), evaluate(ctx, True)
        actor_samples = defaultdict(list)
        for observation in observations:
            people = [
                p for p in observation.detections if p.label == "person" and p.role != "glass"
            ]
            for person in people:
                actor_samples[person.track_id].append(
                    dict(
                        t=observation.timestamp_sec,
                        role=person.role,
                        score=person.score,
                        distinct_cashier=any(
                            p.role == "cashier" and p.track_id != person.track_id for p in people
                        ),
                    )
                )
        rows.append(
            dict(
                videos=aliases[folder.name],
                sha256=folder.name,
                cache=str(path),
                cache_sha256=digest(path),
                before=before,
                after=after,
                expected=expected[folder.name],
                events_unchanged=True,
                actor_samples=dict(actor_samples),
                scene={k: v for k, v in scene.model_dump().items() if k != "candidates"},
                actor_events=[
                    e.model_dump()
                    for e in log.events
                    if e.type in {"ENTER", "EXIT", "ROLE", "HANDOVER", "SECOND_CLIENT_AT_DESK"}
                ],
            )
        )
    metadata = json.loads((args.publication / "metadata.json").read_text())
    mirror_names = {p["video_sha256"]: p for p in metadata["provenance"]}
    mirrored = []
    target_context = None
    for path in sorted((args.publication / "traces").glob("*.json")):
        d = json.loads(path.read_text())
        pin = mirror_names[d["video_sha256"]]
        assert digest(path) == pin["trace_sha256"]
        observations = [
            Observation(
                timestamp_sec=f["t"],
                detections=[
                    Detection(label=p[0], track_id=p[1], role=p[2], box=p[3:7], score=p[7])
                    for p in f["dets"]
                ],
            )
            for f in d["frames"]
        ]
        log = EventLog(
            [Event.model_validate(e) for e in d["events"]],
            d["coverage"],
            d["warnings"],
            d["sessions"],
        )
        ctx = rules.Context(
            codex,
            log,
            observations,
            Scene.model_validate(d["scene"]),
            d["duration_sec"],
            visual_checks=d.get("visual_checks"),
        )
        before, after = [asdict(f) for f in original(ctx)], [asdict(f) for f in candidate(ctx)]
        tracks = defaultdict(list)
        for o in observations:
            people = [p for p in o.detections if p.label == "person" and p.role != "glass"]
            for p in people:
                tracks[p.track_id].append(
                    dict(
                        t=o.timestamp_sec,
                        role=p.role,
                        box=p.box,
                        distinct_cashier=any(
                            q.role == "cashier" and q.track_id != p.track_id for q in people
                        ),
                    )
                )
        mirrored.append(
            dict(
                file=pin["file"],
                trace=str(path),
                trace_sha256=digest(path),
                before=before,
                after=after,
                published_findings=d["findings"],
                actor_samples=dict(tracks),
                mode="Exact existing events/roles rule replay; no event rebuild or video inference",
            )
        )
        if before:
            assert before[0]["rule_id"] == "A-OUTSIDER-ZONE" and not after
            target_context = ctx
    assert target_context is not None
    # One regression: real unsupported episode disappears, independent identity survives an exit.
    claim = original(target_context)[0]
    actor = str(claim.facts["actor_id"])
    ctx = target_context
    assert not candidate(ctx)
    early = Observation(
        timestamp_sec=0,
        detections=[
            Detection(
                label="person", track_id=actor, role="client", score=1, box=(0.1, 0.1, 0.2, 0.3)
            ),
            Detection(
                label="person",
                track_id="separate-cashier",
                role="cashier",
                score=1,
                box=(0.3, 0.1, 0.4, 0.3),
            ),
        ],
    )
    independent = rules.Context(codex, ctx.log, [early, *ctx.observations], ctx.scene, ctx.duration)
    assert [asdict(f) for f in candidate(independent)] == [asdict(f) for f in original(ctx)]
    later = early.model_copy(update={"timestamp_sec": ctx.duration + 1})
    future_only = rules.Context(
        codex, ctx.log, [*ctx.observations, later], ctx.scene, ctx.duration + 2
    )
    assert not candidate(future_only)
    score = {}
    for mode in ("before", "after"):
        confusion = Counter()
        for row in rows:
            pred, gold = bool(row[mode]), row["expected"]
            confusion[("TP" if pred else "FN") if gold else ("FP" if pred else "TN")] += 1
        score[mode] = dict(confusion)
        score[mode]["correct"] = confusion["TP"] + confusion["TN"]
        replay_file = args.out / f"{mode}.jsonl"
        replay_file.write_text(
            "\n".join(
                json.dumps(
                    dict(
                        sha256=row["sha256"],
                        findings=[
                            dict(rule_id=f["rule_id"], t=f["timestamp_sec"]) for f in row[mode]
                        ],
                    )
                )
                for row in rows
            )
            + "\n"
        )
        score_output = io.StringIO()
        with contextlib.redirect_stdout(score_output):
            helper.score(replay_file, args.base / "data/prepared/videos.jsonl")
        (args.out / f"{mode}-score.txt").write_text(score_output.getvalue())
        existing_totals = json.loads(score_output.getvalue().splitlines()[-1])
        assert existing_totals["correct"] == score[mode]["correct"]
        score[mode]["existing_replay_utility"] = existing_totals
    summary = dict(
        base=str(args.base),
        source_commit="4a3b9ea",
        rules_sha256=digest(source),
        cache_clips=len(rows),
        scores=score,
        baseline_matches_requested30=score["before"]["correct"] == 30,
        finding_deltas=[r for r in rows if r["before"] != r["after"]],
        original_clips=rows,
        mirrored_rule_replay=mirrored,
        focused_regression=(
            "PASS: unsupported track rejected; prior separate actor kept after exit; "
            "future evidence rejected"
        ),
        new_video_or_model_run=False,
    )
    (args.out / "results.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in {"original_clips", "mirrored_rule_replay", "finding_deltas"}
            }
        )
    )
    print("original finding deltas", json.dumps(summary["finding_deltas"]))
    print(
        "mirror deltas",
        json.dumps(
            [
                {k: r[k] for k in ("file", "before", "after")}
                for r in mirrored
                if r["before"] != r["after"]
            ]
        ),
    )


if __name__ == "__main__":
    main()
