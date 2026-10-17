"""architecture.md §2: `backend/` must never reference `data/`, label files or `.xlsx` -- the
Excel workbooks and organizer labels are build-time research inputs only, never runtime inputs.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

FORBIDDEN_SUBSTRINGS = ("data/", "open_labels", "gt.json", ".xlsx")


def _python_files() -> list[Path]:
    return sorted(p for p in BACKEND.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_backend_module_references_private_data_or_labels():
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        hits = [s for s in FORBIDDEN_SUBSTRINGS if s in text]
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert not offenders, f"backend/ modules reference private data/labels: {offenders}"


def test_backend_python_files_were_actually_scanned():
    # Guards against an empty glob silently making the test above vacuously true.
    assert len(_python_files()) > 5
