"""`eval.data` manifest checks and `eval.sync_data.pull_missing`, on a synthetic data root."""

from __future__ import annotations

import hashlib
import json

import pytest

from eval.data import check_data_root, load_manifest
from eval.sync_data import pull_missing


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def remote():
    return {"open/videos/X-1.mov": b"one", "open/videos/Х-2.mov": b"two", "team/r.json": b"{}"}


@pytest.fixture
def manifest(remote):
    return {rel: _sha(data) for rel, data in remote.items()}


def test_check_data_root_reports_missing_mismatched_and_unlisted(tmp_path, manifest):
    videos = tmp_path / "open" / "videos"
    videos.mkdir(parents=True)
    (videos / "X-1.mov").write_bytes(b"one")
    (videos / "Х-2.mov").write_bytes(b"tampered")
    (videos / "X-3.mov").write_bytes(b"stray")
    check = check_data_root(tmp_path, manifest)
    assert check.missing == ["team/r.json"]
    assert check.mismatched == ["open/videos/Х-2.mov"]
    assert check.unlisted == ["open/videos/X-3.mov"]
    assert not check.ok


def test_pull_fetches_only_missing_files_and_never_overwrites(tmp_path, remote, manifest):
    (tmp_path / "open" / "videos").mkdir(parents=True)
    local_mismatch = tmp_path / "open" / "videos" / "Х-2.mov"
    local_mismatch.write_bytes(b"local edit")
    fetched = []

    def fetch(rel, dest):
        fetched.append(rel)
        dest.write_bytes(remote[rel])

    pulled, failed = pull_missing(tmp_path, manifest, fetch)
    assert pulled == ["open/videos/X-1.mov", "team/r.json"] and failed == []
    assert fetched == pulled
    assert local_mismatch.read_bytes() == b"local edit"  # reported by the check, not replaced
    assert check_data_root(tmp_path, manifest).mismatched == ["open/videos/Х-2.mov"]
    assert not list(tmp_path.rglob("*.partial"))


def test_pull_discards_downloads_that_fail_verification(tmp_path, manifest):
    def fetch(rel, dest):
        dest.write_bytes(b"corrupted")

    pulled, failed = pull_missing(tmp_path, manifest, fetch)
    assert pulled == [] and len(failed) == 3
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_load_manifest_rejects_paths_outside_the_root(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"files": {"../etc/passwd": "x"}}), "utf-8")
    with pytest.raises(ValueError, match="relative to the data root"):
        load_manifest(path)
