"""The team data root: where organizer data and team workbooks live, and how to verify them.

Layout under the data root (the same on every machine; the team copy is `datathon:~/data`):

    open/open_labels.xlsx                  organizer labels
    open/videos/*.mov                      organizer videos
    team/Таблица_нарушений.xlsx            human annotations
    team/Cash_Discipline_Cases_Rules.xlsx  team workbook (camera layout per clip)
    team/reviews.json                      reviewer decisions on human annotations

`eval/data_manifest.json` pins the SHA-256 of every file. It holds hashes only, so it is tracked.
The root defaults to `<repo>/data` and is overridden with DATATHON_DATA_ROOT.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT_ENV = "DATATHON_DATA_ROOT"
MANIFEST_PATH = Path(__file__).resolve().parent / "data_manifest.json"

ORGANIZER_LABELS = "open/open_labels.xlsx"
VIDEOS_DIR = "open/videos"
HUMAN_ANNOTATIONS = "team/Таблица_нарушений.xlsx"
CASES_WORKBOOK = "team/Cash_Discipline_Cases_Rules.xlsx"
REVIEWS = "team/reviews.json"


def data_root() -> Path:
    return Path(os.environ.get(DATA_ROOT_ENV) or REPO_ROOT / "data").expanduser().resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, str]:
    """Relative path -> SHA-256 of every file the data root must contain."""
    files = json.loads(path.read_text(encoding="utf-8"))["files"]
    if not files:
        raise ValueError(f"{path} lists no files")
    for rel in files:
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise ValueError(f"{path}: manifest path must be relative to the data root: {rel!r}")
    return files


@dataclass
class ManifestCheck:
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    unlisted: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.mismatched or self.unlisted)


def check_data_root(root: Path, manifest: dict[str, str]) -> ManifestCheck:
    """Compare the files under `root` with the manifest. Never modifies anything."""
    check = ManifestCheck()
    for rel, expected in sorted(manifest.items()):
        path = root / rel
        if not path.is_file():
            check.missing.append(rel)
        elif sha256_file(path) != expected:
            check.mismatched.append(rel)
    # A video nobody pinned would silently join the dataset, so unlisted videos are an error.
    videos = root / VIDEOS_DIR
    if videos.is_dir():
        for path in sorted(videos.iterdir()):
            rel = f"{VIDEOS_DIR}/{path.name}"
            if rel not in manifest and not path.name.startswith("."):
                check.unlisted.append(rel)
    return check
