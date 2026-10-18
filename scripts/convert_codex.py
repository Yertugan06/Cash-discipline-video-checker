"""Retired 2026-10-18. Rules no longer come from `data/Cash_Discipline_Cases_Rules.xlsx`: the
rulebook `knowledge/rulebook.yaml` is the one source, and `scripts/build_knowledge.py` generates the
`rules` part of `config/f1_codex.yaml` from it (keeping its `clips` list as it is).
The previous converter is in git history (`git log -p -- scripts/convert_codex.py`).
"""

import sys

sys.exit("convert_codex.py is retired: edit knowledge/rulebook.yaml, run build_knowledge.py")
