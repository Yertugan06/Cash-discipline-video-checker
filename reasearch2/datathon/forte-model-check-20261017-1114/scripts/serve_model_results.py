"""Serve a local model-check HTML page, results and live logs using only the stdlib."""

import argparse
import json
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOGS = (
    "build.log",
    "download.log",
    "model-check/run.log",
    "model-check.log",
    "synthetic-pipeline/run.log",
    "pipeline-console.log",
    "service.log",
    "eval.log",
    "first-video.log",
)


def progress(directory: Path, hardware: str) -> dict:
    reports = {}
    for name in ("model-check", "synthetic-pipeline"):
        path = directory / name / "result.json"
        if path.is_file():
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
    logs = [name for name in LOGS if (directory / name).is_file()]
    evaluation_path = directory / "gpu/progress.json"
    evaluation = (
        json.loads(evaluation_path.read_text(encoding="utf-8"))
        if evaluation_path.is_file()
        else None
    )
    if any(report.get("status") == "failed" for report in reports.values()):
        stage = "failed"
    elif reports.get("synthetic-pipeline", {}).get("status") == "passed":
        stage = "done"
    elif reports.get("model-check", {}).get("status") == "passed":
        stage = "pipeline"
    elif "model-check/run.log" in logs:
        stage = "models"
    else:
        stage = "building"
    if evaluation:
        stage = "evaluated" if evaluation["status"] == "done" else "evaluating"
    latest = max(
        ((directory / name).stat().st_mtime for name in logs), default=directory.stat().st_mtime
    )
    return {
        "stage": stage,
        "hardware": hardware,
        "note": "Model probes use synthetic input. Dataset evaluation runs on this cloud VM.",
        "updated_at": datetime.fromtimestamp(latest).astimezone().isoformat(),
        "logs": logs,
        "models_ready": "model-check" in reports,
        "pipeline_ready": "synthetic-pipeline" in reports,
        "evaluation": evaluation,
        "evaluation_report_ready": (directory / "gpu/index.html").is_file(),
        "app_ready": (directory / "service.json").is_file(),
        "first_report_ready": (directory / "first-video/index.html").is_file(),
    }


class ResultsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, hardware: str, **kwargs):
        self.hardware = hardware
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/progress.json":
            return super().do_GET()
        try:
            payload = json.dumps(progress(Path(self.directory), self.hardware)).encode()
        except (OSError, ValueError) as exc:
            self.send_error(500, str(exc))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--hardware", default="Local model check")
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("--directory must exist")
    handler = partial(
        ResultsHandler, directory=str(args.directory.resolve()), hardware=args.hardware
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Results: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
