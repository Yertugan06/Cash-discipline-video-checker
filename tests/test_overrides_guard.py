"""`config/overrides.yaml` hand-tunes calibration per video SHA-256. An entry for an organizer
video would tune the service on the very clips it is scored on (dev and lockbox), so no key may be
the hash of any file pinned in `eval/data_manifest.json`."""

from __future__ import annotations

from pathlib import Path

import yaml

from eval.data import load_manifest

OVERRIDES = Path(__file__).resolve().parent.parent / "config" / "overrides.yaml"


def _leaked(videos: dict, pinned: set[str]) -> list[str]:
    return sorted(str(k) for k in videos if str(k).lower() in pinned)


def test_overrides_never_name_an_organizer_video():
    videos = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["videos"] or {}
    leaked = _leaked(videos, set(load_manifest().values()))
    assert not leaked, f"overrides.yaml tunes organizer videos: {leaked}"


def test_guard_catches_a_pinned_hash_in_any_case():
    pinned = set(load_manifest().values())
    some = next(iter(pinned))
    assert _leaked({some.upper(): {}, "0" * 64: {}}, pinned) == [some.upper()]
