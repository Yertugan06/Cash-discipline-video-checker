"""Download only pinned, permissively licensed artifacts; no inference performs downloads."""

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(item: tuple[dict, dict], destination: Path) -> tuple[str, str]:
    model, artifact = item
    path = destination / model["name"] / artifact["path"]
    expected = artifact["sha256"]
    if (
        path.is_file()
        and path.stat().st_size == artifact["size"]
        and (not expected or sha256(path) == expected)
    ):
        return path.relative_to(destination).as_posix(), sha256(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{artifact['path']}"
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if artifact["size"] is not None and temporary.stat().st_size != artifact["size"]:
            raise ValueError(f"Size mismatch: {model['name']}/{artifact['path']}")
        checksum = sha256(temporary)
        if expected and checksum != expected:
            raise ValueError(f"SHA-256 mismatch: {model['name']}/{artifact['path']}")
        temporary.replace(path)
        print(f"Downloaded {model['name']}/{artifact['path']}", flush=True)
        return path.relative_to(destination).as_posix(), checksum
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest", type=Path, default=Path(os.environ.get("WEIGHTS_DIR", ROOT / "weights"))
    )
    args = parser.parse_args()
    manifest = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    if any(model["license"] not in {"mit", "apache-2.0"} for model in manifest["models"]):
        raise ValueError("Unapproved checkpoint licence; ask the user before downloading")
    items = [(model, artifact) for model in manifest["models"] for artifact in model["files"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        hashes = dict(pool.map(lambda item: download(item, args.dest), items))
    manifest["downloaded_sha256"] = hashes
    (args.dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Weights verified. Inference can now run offline.")


if __name__ == "__main__":
    main()
