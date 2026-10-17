"""Consistency checks on the real team data root. Skipped where the data is absent (CI, fresh
checkouts). Assertions print counts and clip IDs only, never label values."""

from __future__ import annotations

import json

import pytest

from eval.data import check_data_root, data_root, load_manifest
from eval.ground_truth import DEFAULT_OUT, build_ground_truth, load_sources, split_problems

ROOT = data_root()
MANIFEST = load_manifest()
CHECK = check_data_root(ROOT, MANIFEST) if ROOT.is_dir() else None

pytestmark = pytest.mark.skipif(
    CHECK is None or bool(CHECK.missing),
    reason=f"team data root {ROOT} absent or incomplete (python -m eval.sync_data --pull)",
)


@pytest.fixture(scope="module")
def built():
    sources = load_sources(ROOT, MANIFEST)
    gt = json.loads(json.dumps(build_ground_truth(ROOT, *sources), ensure_ascii=False))
    return sources, gt


def test_data_root_matches_manifest():
    assert CHECK.ok, f"mismatched {CHECK.mismatched}, unlisted {CHECK.unlisted}"


def test_every_video_has_exactly_one_organizer_label(built):
    (videos, organizer, *_), _ = built
    assert len(videos) == 42
    assert {v.clip_id for v in videos} == set(organizer)


def test_duplicates_collapse_and_keep_provenance(built):
    _, gt = built
    assert len(gt) == 40
    assert sum(len(c["files"]) for c in gt.values()) == 42
    assert {k: c["dups"] for k, c in gt.items() if len(c["dups"]) > 1} == {
        "X-4": ["X-4", "X-47"],
        "X-5": ["X-5", "X-48"],
    }


def test_frozen_split_still_follows(built):
    _, gt = built
    frozen = json.loads((DEFAULT_OUT / "split.json").read_text(encoding="utf-8"))
    assert split_problems(gt, frozen) == []


def test_written_gt_is_current(built):
    _, gt = built
    written = json.loads((DEFAULT_OUT / "gt.json").read_text(encoding="utf-8"))
    stale = sorted(k for k in gt if written.get(k) != gt[k])
    assert set(written) == set(gt) and not stale, f"gt.json stale for {stale}: rerun --write"
