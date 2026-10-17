"""Verify the local data root against the manifest, and optionally pull missing files from the team
copy on the Brev VM.

Read-only by default: without --pull nothing is written anywhere. --pull only downloads files that
are missing locally, verifies each against its pinned SHA-256 before moving it into place, and
never overwrites an existing file (a mismatched local file is reported, not replaced). Nothing is
ever written to the VM.

Usage:
    .venv/bin/python -m eval.sync_data            # check the local data root
    .venv/bin/python -m eval.sync_data --remote   # also check the team copy on the VM
    .venv/bin/python -m eval.sync_data --pull     # download what is missing locally
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from eval.data import ManifestCheck, check_data_root, data_root, load_manifest, sha256_file

DEFAULT_HOST = "datathon"
DEFAULT_REMOTE_ROOT = "data"  # relative to the remote home directory

Fetch = Callable[[str, Path], None]


def _remote_path(remote_root: str, rel: str) -> str:
    return shlex.quote(f"{remote_root}/{rel}")


def remote_hashes(host: str, remote_root: str, rels: list[str]) -> dict[str, str]:
    """SHA-256 of each file that exists on the VM; files that are absent are left out."""
    quoted = " ".join(_remote_path(remote_root, rel) for rel in rels)
    cmd = f'cd && for f in {quoted}; do [ -f "$f" ] && sha256sum -- "$f"; done; true'
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, cmd],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    ).stdout
    prefix = f"{remote_root}/"
    hashes = {}
    for line in out.splitlines():
        digest, _, name = line.partition("  ")
        hashes[name.removeprefix(prefix)] = digest
    return hashes


def check_remote(host: str, remote_root: str, manifest: dict[str, str]) -> ManifestCheck:
    hashes = remote_hashes(host, remote_root, sorted(manifest))
    check = ManifestCheck()
    for rel, expected in sorted(manifest.items()):
        if rel not in hashes:
            check.missing.append(rel)
        elif hashes[rel] != expected:
            check.mismatched.append(rel)
    return check


def ssh_fetch(host: str, remote_root: str) -> Fetch:
    def fetch(rel: str, dest: Path) -> None:
        with dest.open("xb") as f:
            subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    host,
                    f"cd && cat -- {_remote_path(remote_root, rel)}",
                ],
                stdout=f,
                check=True,
                timeout=600,
            )

    return fetch


def pull_missing(root: Path, manifest: dict[str, str], fetch: Fetch) -> tuple[list[str], list[str]]:
    """Download every manifest file absent under `root`. Returns (pulled, failed)."""
    pulled, failed = [], []
    for rel, expected in sorted(manifest.items()):
        dest = root / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".partial")
        partial.unlink(missing_ok=True)
        try:
            fetch(rel, partial)
            if sha256_file(partial) != expected:
                failed.append(rel)
                continue
            os.link(partial, dest)  # fails instead of overwriting if dest appeared meanwhile
            pulled.append(rel)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"pull failed: {rel}: {exc}", file=sys.stderr)
            failed.append(rel)
        finally:
            partial.unlink(missing_ok=True)
    return pulled, failed


def _report(where: str, check: ManifestCheck, total: int) -> None:
    print(f"{where}: {total - len(check.missing) - len(check.mismatched)}/{total} files verified")
    for label, rels in (
        ("missing", check.missing),
        ("SHA-256 mismatch", check.mismatched),
        ("not in manifest", check.unlisted),
    ):
        for rel in rels:
            print(f"  {label}: {rel}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--remote", action="store_true", help="also verify the team copy on the VM")
    ap.add_argument("--pull", action="store_true", help="download files missing locally")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    args = ap.parse_args(argv)

    manifest = load_manifest()
    root = data_root()
    ok = True
    if args.remote:
        remote = check_remote(args.host, args.remote_root, manifest)
        _report(f"{args.host}:~/{args.remote_root}", remote, len(manifest))
        ok &= remote.ok
    if args.pull:
        pulled, failed = pull_missing(root, manifest, ssh_fetch(args.host, args.remote_root))
        print(f"pulled {len(pulled)} file(s), {len(failed)} failed")
        for rel in failed:
            print(f"  failed: {rel}")
        ok &= not failed
    local = check_data_root(root, manifest)
    _report(str(root), local, len(manifest))
    ok &= local.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
