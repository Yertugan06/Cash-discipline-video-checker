"""Install the validated VM-private mirror bundle without changing the live run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create_verified(source: Path, target: Path) -> None:
    if target.exists():
        if digest(source) != digest(target):
            raise FileExistsError(f"Different existing artifact: {target.name}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".a23-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream, source.open("rb") as incoming:
            import shutil

            shutil.copyfileobj(incoming, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if digest(Path(temporary)) != digest(source):
            raise ValueError("Copied artifact hash mismatch")
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    os.umask(0o077)
    shared = Path.home() / "workspaces/datathon26-workers/shared"
    base = shared / "a23/base"
    bundle = shared / "a23-mirrored-publication"
    state = base / "runtime/realtime"
    assert (state / ".attempt-metadata-ready").is_file()
    sys.path.insert(0, str(base))
    from realtime.gateway import Item

    untouched = [state / "state.live.json"]
    for directory in (state / "annotations", state / "descriptions"):
        untouched.extend(directory.glob("*.json"))
    before = {str(path): digest(path) for path in untouched}
    rows = json.loads((bundle / "realtime/state.a23-mirrored.json").read_text())
    assert len(rows) == 8
    metadata = json.loads((bundle / "metadata.json").read_text())
    assert metadata["gateway_Item_validated"] == 8
    for row, provenance in zip(rows, metadata["provenance"], strict=True):
        item = Item.model_validate(row)
        assert item.status == "done" and item.id == provenance["id"]
        assert re.fullmatch(r"a23-mirrored-\d{2}", item.id)
        assert re.fullmatch(r"[0-9a-f]{32}", item.job_id or "")
        source = bundle / "realtime/uploads" / f"{item.id}.mov"
        assert digest(source) == provenance["video_sha256"]
        create_verified(source, state / "uploads" / source.name)
        trace = bundle / "traces" / f"{item.job_id}.json"
        assert digest(trace) == provenance["trace_sha256"]
        create_verified(trace, base / "runtime/traces" / trace.name)
    for name in ("state.a23-mirrored.json", "state.a23-mirrored.meta.json"):
        create_verified(bundle / "realtime" / name, state / name)
    assert before == {str(path): digest(path) for path in untouched}
    print(json.dumps({"published_run": "a23-mirrored", "items": 8,
                      "preserved_files": len(before), "score": metadata["score"]}))


if __name__ == "__main__":
    main()
