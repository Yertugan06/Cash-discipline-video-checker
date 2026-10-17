"""Codex lookup: rule citations come from codex_verified.json by ID (copied read-only into data/)."""
import json
import re
from functools import lru_cache
from pathlib import Path

CODEX = Path(__file__).resolve().parents[1] / "data" / "codex_verified.json"
ACT_NAMES = {
    "231": "Постановление Правления НБРК от 29.11.2019 № 231 (Правила кассовых операций)",
    "14": "Постановление Правления НБРК от 24.02.2020 № 14 (требования к помещениям)",
    "53": "Постановление АРРФР от 03.04.2026 № 53 (требования к ИБ)",
}


@lru_cache(maxsize=1)
def codex():
    return {r["id"]: r for r in json.loads(CODEX.read_text(encoding="utf-8"))}


def citation(cid):
    r = codex()[cid]
    return {"id": cid, "act": ACT_NAMES.get(r["act"], r["act"]), "clause": r["punkt"], "strength": r["strength"],
            "quote": r["quote"], "url": r["url"]}


def scorer_code(cid):
    """Scorer matches clause numbers; use the act-agnostic clause text (e.g. 'п. 71 пп. 9)')."""
    r = codex()[cid]
    if r["act"] in ("231", "14"):
        return r["act"] + "-" + "-".join(re.findall(r"\d+", r["punkt"]))
    return r["punkt"]
