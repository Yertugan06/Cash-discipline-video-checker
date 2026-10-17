"""Run local inference on unique files and write transparent evaluation reports."""

import argparse
from pathlib import Path

from backend.codex import load_codex
from backend.eval_runner import evaluate, evaluation_settings
from backend.report import write_reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--codex", type=Path, default=Path("codex.yaml"))
    parser.add_argument("--fps", type=float, default=5)
    parser.add_argument("--via-api", action="store_true")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--held-out-layout", default="Desk near the door")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--weights", type=Path, default=Path("weights"))
    parser.add_argument("--perception-config", type=Path, default=Path("config/perception.yaml"))
    parser.add_argument("--overrides", type=Path, default=Path("config/overrides.yaml"))
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument(
        "--reuse-perception",
        action="store_true",
        help="Replay cached model observations; timings are not an uncached inference benchmark",
    )
    args = parser.parse_args()
    try:
        rows, summaries = evaluate(
            args.videos,
            args.labels,
            args.out,
            evaluation_settings(
                args.codex,
                args.fps,
                device=args.device,
                weights_dir=args.weights,
                perception_config=args.perception_config,
                overrides_path=args.overrides,
                timeout_sec=args.timeout,
                reuse_perception=args.reuse_perception,
            ),
            via_api=args.via_api,
            api_url=args.api_url,
            debug=args.debug,
            held_out_layout=args.held_out_layout,
        )
        write_reports(args.out, rows, summaries, load_codex(args.codex))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Evaluation error: {exc}\n")
    for summary in summaries:
        print({key: value for key, value in summary.items() if key != "per_rule"})
    if any(row["status"] == "failed" for row in rows):
        parser.exit(1, "Some videos failed; inspect per_video.csv and index.html\n")


if __name__ == "__main__":
    main()
