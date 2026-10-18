"""Build the legal catalog from the stored texts of the acts and check the rulebook against them.

Inputs (hand-maintained):
  knowledge/sources/sources.yaml          where each act's text came from; repealed acts
  knowledge/sources/<act>/source.docx     the adilet.zan.kz text, kept byte-for-byte
  knowledge/legal_review.yaml             per punkt: applies to the cash desk? can video show it?
  knowledge/legal_requirements.yaml       atomic requirements derived from the law, each with a
                                          decision against the rulebook and the detector
  knowledge/rulebook.yaml                 the rules and the norm quotes they cite (the one source)
  backend/f1/rules.py, backend/f1/events.py   what the deployed detector can actually emit

Outputs (generated, never edit by hand):
  knowledge/sources/<act>/text.txt        the act as plain text, numbering restored
  knowledge/legal_catalog.json            every punkt, part and subpunkt with its review
  knowledge/active_rules.json             enabled rules, their norms and the source check
  knowledge/event_mapping.json            F1 events and objects each rule consumes
  knowledge/legal_audit.md                what was checked, what failed, what is excluded
  knowledge/coverage_matrix.md            law -> video event -> F1 signals -> rule -> tests

The runtime never reads these files; it reads the Knowledge Pack built by build_knowledge.py.

    .venv/bin/python scripts/build_legal_catalog.py           # regenerate
    .venv/bin/python scripts/build_legal_catalog.py --check   # fail if an output is stale
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_knowledge import load_rulebook  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
SOURCES = KNOWLEDGE / "sources"
REVIEW = KNOWLEDGE / "legal_review.yaml"
REQUIREMENTS = KNOWLEDGE / "legal_requirements.yaml"
TESTS = ROOT / "tests"
F1_RULES = ROOT / "backend" / "f1" / "rules.py"
F1_EVENTS = ROOT / "backend" / "f1" / "events.py"
PERCEPTION = ROOT / "config" / "perception.yaml"
ROLES = {"cashier", "client", "collector", "outsider", "visitor"}  # backend/f1/events.py roles

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

APPLICABILITY = {"cash_desk", "premises", "workstation", "back_office", "not_applicable"}
OBSERVABILITY = {"direct", "conditional", "partial", "not_observable", "too_long"}
STATUS = {"linked", "candidate", "weak", "excluded"}
DECISIONS = {
    "implemented": "already implemented, basis holds",
    "implemented_weak": "implemented, but the basis or the detection logic is incomplete",
    "new_existing_signals": "new rule the current F1 signals support",
    "new_needs_logic": "new rule that needs extra detection or temporal logic",
    "not_verifiable": "cannot be established reliably from the video",
    "not_applicable": "legally uncertain or not about the cash desk",
}
MODEL_SUPPORT = {"yes", "partial", "no"}
REQUIREMENT_FIELDS = (
    "id unit quote subject kind requirement conditions breach_visual signals evidence "
    "insufficient_when observability plausible_in_dataset model_support decision rules "
    "decision_note"
).split()


# --- docx -> lines -------------------------------------------------------------------------


def _numbering(archive: zipfile.ZipFile) -> dict[str, dict[int, tuple[int, str, str]]]:
    """numId -> ilvl -> (start, format, text template) from word/numbering.xml."""
    root = ElementTree.fromstring(archive.read("word/numbering.xml"))
    abstract = {}
    for item in root.iter(W + "abstractNum"):
        levels = {}
        for level in item.findall(W + "lvl"):
            start, fmt, text = (
                level.find(W + "start"),
                level.find(W + "numFmt"),
                level.find(W + "lvlText"),
            )
            levels[int(level.get(W + "ilvl"))] = (
                int(start.get(W + "val")) if start is not None else 1,
                fmt.get(W + "val") if fmt is not None else "decimal",
                text.get(W + "val") if text is not None else "",
            )
        abstract[item.get(W + "abstractNumId")] = levels
    numbering = {}
    for item in root.iter(W + "num"):
        levels = dict(abstract[item.find(W + "abstractNumId").get(W + "val")])
        for override in item.findall(W + "lvlOverride"):
            ilvl, start = int(override.get(W + "ilvl")), override.find(W + "startOverride")
            if start is not None:
                _, fmt, text = levels[ilvl]
                levels[ilvl] = (int(start.get(W + "val")), fmt, text)
        numbering[item.get(W + "numId")] = levels
    return numbering


def docx_lines(path: Path) -> list[str]:
    """Paragraph texts with Word's automatic list numbers written out ("20. ", "9) ")."""
    with zipfile.ZipFile(path) as archive:
        numbering = _numbering(archive)
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    counters: dict[str, dict[int, int]] = {}
    lines = []
    for paragraph in document.iter(W + "p"):
        text = "".join(
            (node.text or "") if node.tag == W + "t" else "\n" if node.tag == W + "br" else ""
            for node in paragraph.iter()
        )
        prefix = ""
        properties = paragraph.find(f"{W}pPr/{W}numPr")
        if properties is not None and properties.find(W + "numId") is not None:
            num_id = properties.find(W + "numId").get(W + "val")
            ilvl_node = properties.find(W + "ilvl")
            ilvl = int(ilvl_node.get(W + "val")) if ilvl_node is not None else 0
            if num_id in numbering and ilvl in numbering[num_id]:
                levels, count = numbering[num_id], counters.setdefault(num_id, {})
                for deeper in [k for k in count if k > ilvl]:
                    del count[deeper]
                count[ilvl] = count.get(ilvl, levels[ilvl][0] - 1) + 1
                _, fmt, template = levels[ilvl]
                if fmt != "bullet":
                    prefix = (
                        re.sub(
                            r"%(\d)",
                            lambda m, count=count, levels=levels: str(
                                count.get(int(m.group(1)) - 1, levels[int(m.group(1)) - 1][0])
                            ),
                            template,
                        )
                        + " "
                    )
        for part in text.split("\n"):
            lines.append(prefix + part.strip())
            prefix = ""
    return lines


PAGE_FOOTER = re.compile(r"^\d+ / \d+$")
PUNKT = re.compile(r"^(\d+)\. ")
INSERTED = re.compile(r"^(\d+)-(\d+)\. ")  # a punkt added by an amendment: "53-1. ..."
SUBPUNKT = re.compile(r"^(\d+)\) ")
FOOTNOTE = re.compile(r"^Сноска\.")
HEADING = re.compile(r"^(Глава|Параграф|Раздел) \d+")


def clean_lines(raw: list[str]) -> list[str]:
    """Drop page footers and blank lines; rejoin lines the PDF conversion split mid-sentence."""
    lines: list[str] = []
    for line in raw:
        if not line or PAGE_FOOTER.match(line):
            continue
        structural = (
            PUNKT.match(line)
            or INSERTED.match(line)
            or SUBPUNKT.match(line)
            or FOOTNOTE.match(line)
            or HEADING.match(line)
        )
        if lines and not structural and lines[-1][-1] not in '.;:!?"»':
            lines[-1] += " " + line
        else:
            lines.append(line)
    return lines


# --- lines -> units --------------------------------------------------------------------------


@dataclass
class Punkt:
    act: str
    number: int
    chapter: str
    parts: list[str] = field(default_factory=list)
    inserted: int = 0  # 1 for "53-1", 0 for an original punkt
    subpunkts: list[tuple[int, int, str]] = field(default_factory=list)  # (number, part, text)
    footnotes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.act}-{self.label}"

    @property
    def label(self) -> str:
        return f"{self.number}-{self.inserted}" if self.inserted else str(self.number)

    @property
    def text(self) -> str:
        lines = []
        for index, part in enumerate(self.parts, 1):
            lines.append(part)
            lines += [text for _, at, text in self.subpunkts if at == index]
        return "\n".join(lines)


def _rules_body(lines: list[str]) -> tuple[int, int]:
    """[start, end) of the longest run of consecutively numbered punkts: the Правила/Требования
    themselves, as opposed to the постановление's own short list and the appendices."""
    best, run = (0, 0, 0), None
    for index, line in enumerate(lines):
        match = PUNKT.match(line)
        if not match:
            continue
        number = int(match.group(1))
        if run and number == run[2] + 1:
            run = (run[0], index, number)
        elif number == 1:
            run = (index, index, 1)
        else:
            continue
        if run[2] > best[2]:
            best = run
    start, last, _ = best
    end = next(
        (i for i in range(last + 1, len(lines)) if lines[i].startswith("Приложение")), len(lines)
    )
    return start, end


def segment(act: str, lines: list[str]) -> list[Punkt]:
    start, end = _rules_body(lines)
    chapter = next((line for line in reversed(lines[:start]) if HEADING.match(line)), "")
    punkts: list[Punkt] = []
    for line in lines[start:end]:
        match = PUNKT.match(line)
        inserted = INSERTED.match(line)
        if match and int(match.group(1)) == (punkts[-1].number + 1 if punkts else 1):
            punkts.append(Punkt(act, int(match.group(1)), chapter, [line]))
        elif (
            inserted
            and punkts
            and int(inserted.group(1)) == punkts[-1].number
            and int(inserted.group(2)) == punkts[-1].inserted + 1
        ):
            punkts.append(
                Punkt(act, punkts[-1].number, chapter, [line], inserted=int(inserted.group(2)))
            )
        elif HEADING.match(line):
            chapter = line
        elif FOOTNOTE.match(line):
            punkts[-1].footnotes.append(line)
        elif sub := SUBPUNKT.match(line):
            punkts[-1].subpunkts.append((int(sub.group(1)), len(punkts[-1].parts), line))
        elif punkts[-1].footnotes:
            punkts[-1].footnotes[-1] += " " + line  # a footnote's own second paragraph
        else:
            punkts[-1].parts.append(line)
    return punkts


AMENDMENT = re.compile(r"от (\d{2})\.(\d{2})\.(\d{4}) № (\d+)")


def latest_amendment(lines: list[str]) -> str | None:
    found = {
        (y, m, d, n)
        for line in lines
        if line.startswith("Сноска")
        for d, m, y, n in AMENDMENT.findall(line)
    }
    if not found:
        return None
    y, m, d, n = max(found)
    return f"{d}.{m}.{y} № {n}"


# --- rulebook norms vs. the text ------------------------------------------------------------


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е").replace("«", '"').replace("»", '"')
    text = re.sub(r"[–—-]+", "-", text)
    return re.sub(r"\s+", " ", text).strip()


CITATION = re.compile(r"п\. (\d+(?:-\d+)?)(?: ч\. (\d+))?(?: пп\. (\d+)\))?")


def locate(punkts: dict[str, Punkt], act: str, punkt: str) -> tuple[str, str] | None:
    """The catalog unit id and text that a rulebook `punkt` string ("п. 20 ч. 2") points at."""
    match = CITATION.fullmatch(punkt.strip())
    if not match or f"{act}-{match.group(1)}" not in punkts:
        return None
    item = punkts[f"{act}-{match.group(1)}"]
    if match.group(3):
        number = int(match.group(3))
        texts = [text for n, _, text in item.subpunkts if n == number]
        return (f"{item.id}-s{number}", texts[0]) if texts else None
    if match.group(2):
        index = int(match.group(2))
        if index > len(item.parts):
            return None
        return f"{item.id}-c{index}", "\n".join(
            [item.parts[index - 1]] + [text for _, at, text in item.subpunkts if at == index]
        )
    return item.id, item.text


def check_norm(punkts: dict[str, Punkt], acts: set[str], repealed: dict, norm) -> dict:
    if norm.act in repealed:
        return {
            "result": "repealed_act",
            "detail": f"act {norm.act} is repealed by act {repealed[norm.act]['repealed_by']}",
        }
    if norm.act not in acts:
        return {"result": "no_source_text", "detail": f"no stored text for act {norm.act}"}
    expected_document = SOURCES_META["acts"][norm.act]["document_id"]
    if expected_document not in str(norm.url):
        return {
            "result": "wrong_document_url",
            "detail": f"url does not point at {expected_document}",
        }
    quote = normalize(norm.quote)
    cited = locate(punkts, norm.act, norm.punkt)
    if cited and quote in normalize(cited[1]):
        return {"result": "quote_in_cited_unit", "unit": cited[0]}
    elsewhere = [p.id for p in punkts.values() if p.act == norm.act and quote in normalize(p.text)]
    if elsewhere:
        return {
            "result": "quote_in_other_unit",
            "unit": cited[0] if cited else None,
            "found_in": elsewhere,
            "detail": f"quote is verbatim in {', '.join(elsewhere)}, not in '{norm.punkt}'",
        }
    return {
        "result": "quote_not_found",
        "unit": cited[0] if cited else None,
        "detail": "quote is not verbatim in the act",
    }


# --- what the F1 detector consumes ----------------------------------------------------------


def f1_capabilities() -> dict[str, dict]:
    """Per rule id in backend/f1/rules.py RULES: the event kinds, object labels, state families
    and coverage flags its evaluator (and the module-level helpers it calls) reads, plus the event
    kinds named inside the Context methods it calls (`ctx.leaves()`, `ctx.room_exits()`). Objects
    are the detector's labels in config/perception.yaml."""
    tree = ast.parse(F1_RULES.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    context = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Context")
    methods = {n.name: n for n in context.body if isinstance(n, ast.FunctionDef)}
    event_kinds = set(re.findall(r'"([A-Z][A-Z_]{2,})"', F1_EVENTS.read_text(encoding="utf-8")))
    perception = yaml.safe_load(PERCEPTION.read_text(encoding="utf-8"))
    labels = set(perception["object_prompts"]) | set(perception["scene_prompts"])
    registry = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "RULES" for t in node.targets)
    )

    def reads(name: str, seen: set[str]) -> dict[str, set[str]]:
        found = {
            "events": set(),
            "objects": set(),
            "roles": set(),
            "states": set(),
            "coverage": set(),
        }
        if name in seen or name not in functions:
            return found
        seen.add(name)
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call):
                callee = node.func
                attribute = (
                    callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
                )
                first = node.args[0] if node.args else None
                literal = (
                    first.value
                    if isinstance(first, ast.Constant) and isinstance(first.value, str)
                    else None
                )
                if attribute == "state_at" and literal:
                    found["states"].add(literal)
                if attribute == "get" and literal and "coverage" in ast.unparse(callee):
                    found["coverage"].add(literal)
                if isinstance(callee, ast.Name):
                    for key, values in reads(callee.id, seen).items():
                        found[key] |= values
                if isinstance(callee, ast.Attribute) and attribute in methods:
                    found["events"] |= {
                        n.value
                        for n in ast.walk(methods[attribute])
                        if isinstance(n, ast.Constant) and n.value in event_kinds
                    }
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in event_kinds:
                    found["events"].add(node.value)
                elif node.value in labels:
                    found["objects"].add(node.value)
                elif node.value in ROLES:
                    found["roles"].add(node.value)
        return found

    result = {}
    for key, value in zip(registry.keys, registry.values, strict=True):
        found = reads(value.id, set())
        found["objects"] -= found["states"] | found["coverage"]
        result[key.value] = {
            "evaluator": f"backend/f1/rules.py:{value.id}",
            **{k: sorted(v) for k, v in found.items()},
        }
    return result


# --- assembly --------------------------------------------------------------------------------

SOURCES_META: dict = {}


def load_review(punkts: dict[str, Punkt], rule_ids: set[str]) -> dict[str, dict]:
    review = yaml.safe_load(REVIEW.read_text(encoding="utf-8")) or {}
    units = review.get("units", {})
    known = (
        set(punkts)
        | {f"{p.id}-s{n}" for p in punkts.values() for n, _, _ in p.subpunkts}
        | {f"{p.id}-c{i}" for p in punkts.values() for i in range(1, len(p.parts) + 1)}
    )
    for unit_id, entry in units.items():
        if unit_id not in known:
            raise ValueError(f"legal_review.yaml: unknown unit {unit_id}")
        for key, allowed in (
            ("applicability", APPLICABILITY),
            ("observability", OBSERVABILITY),
            ("status", STATUS),
        ):
            if entry.get(key) not in allowed:
                raise ValueError(
                    f"legal_review.yaml: {unit_id}.{key} must be one of {sorted(allowed)}"
                )
        if not entry.get("reason"):
            raise ValueError(f"legal_review.yaml: {unit_id} needs a reason")
        if unknown := set(entry.get("rules", [])) - rule_ids:
            raise ValueError(f"legal_review.yaml: {unit_id} names unknown rules {sorted(unknown)}")
    return units


def unit_text(punkts: dict[str, Punkt], unit_id: str) -> str | None:
    match = re.fullmatch(r"(\d+-\d+(?:-\d+)?)(?:-([cs])(\d+))?", unit_id)
    if not match or match.group(1) not in punkts:
        return None
    item, kind, number = punkts[match.group(1)], match.group(2), match.group(3)
    if not kind:
        return item.text
    if kind == "s":
        texts = [t for n, _, t in item.subpunkts if n == int(number)]
        return texts[0] if texts else None
    index = int(number)
    if index > len(item.parts):
        return None
    return "\n".join([item.parts[index - 1]] + [t for _, at, t in item.subpunkts if at == index])


def load_requirements(punkts: dict[str, Punkt], rule_ids: set[str]) -> list[dict]:
    if not REQUIREMENTS.exists():
        return []
    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))["requirements"]
    seen = set()
    for item in requirements:
        where = f"legal_requirements.yaml: {item.get('id')}"
        if missing := [k for k in REQUIREMENT_FIELDS if k not in item]:
            raise ValueError(f"{where} lacks {missing}")
        if item["id"] in seen:
            raise ValueError(f"{where} is duplicated")
        seen.add(item["id"])
        text = unit_text(punkts, item["unit"])
        if text is None:
            raise ValueError(f"{where}: unknown unit {item['unit']}")
        if normalize(item["quote"]) not in normalize(text):
            raise ValueError(f"{where}: quote is not verbatim in {item['unit']}")
        if item["decision"] not in DECISIONS or item["model_support"] not in MODEL_SUPPORT:
            raise ValueError(f"{where}: bad decision or model_support")
        if item["observability"] not in OBSERVABILITY:
            raise ValueError(f"{where}: bad observability")
        if unknown := set(item["rules"]) - rule_ids:
            raise ValueError(f"{where} names unknown rules {sorted(unknown)}")
        if item["decision"].startswith("implemented") and not item["rules"]:
            raise ValueError(f"{where}: an implemented requirement names its rules")
    return requirements


def build() -> dict[Path, str]:
    SOURCES_META.clear()
    SOURCES_META.update(yaml.safe_load((SOURCES / "sources.yaml").read_text(encoding="utf-8")))
    rulebook = load_rulebook()
    outputs: dict[Path, str] = {}
    punkts: dict[str, Punkt] = {}
    acts = {}
    for act, meta in SOURCES_META["acts"].items():
        docx = SOURCES / act / "source.docx"
        lines = clean_lines(docx_lines(docx))
        outputs[SOURCES / act / "text.txt"] = "\n".join(lines) + "\n"
        segmented = segment(act, lines)
        punkts.update({p.id: p for p in segmented})
        acts[act] = {
            **meta,
            "title": rulebook.acts[act].document_title if act in rulebook.acts else lines[0],
            "header": " ".join(lines[1:3]),
            "latest_amendment_in_footnotes": latest_amendment(lines),
            "punkts": len(segmented),
            "source_sha256": hashlib.sha256(docx.read_bytes()).hexdigest(),
        }

    repealed = SOURCES_META.get("repealed", {})
    review = load_review(punkts, set(rulebook.rules))
    requirements = load_requirements(punkts, set(rulebook.rules))
    checks = {
        norm_id: check_norm(punkts, set(acts), repealed, norm)
        for norm_id, norm in rulebook.norms.items()
    }
    capabilities = f1_capabilities()

    cited_by: dict[str, list[str]] = {}
    for rule_id, rule in rulebook.rules.items():
        for norm_id in rule.norms:
            unit = checks[norm_id].get("unit")
            if unit:
                cited_by.setdefault(re.sub(r"-[cs]\d+$", "", unit), []).append(rule_id)

    units = []
    for item in punkts.values():
        entry = {
            "id": item.id,
            "act": item.act,
            "punkt": item.label,
            "chapter": item.chapter,
            "text": item.text,
            "parts": [{"id": f"{item.id}-c{i}", "text": t} for i, t in enumerate(item.parts, 1)],
            "subpunkts": [
                {"id": f"{item.id}-s{n}", "part": at, "text": t} for n, at, t in item.subpunkts
            ],
            "footnotes": item.footnotes,
            "cited_by_rules": sorted(set(cited_by.get(item.id, []))),
            "review": review.get(item.id),
        }
        overrides = {
            k: v for k, v in review.items() if k.startswith((item.id + "-c", item.id + "-s"))
        }
        if overrides:
            entry["sub_reviews"] = overrides
        units.append(entry)

    catalog = {
        "generated_by": "scripts/build_legal_catalog.py",
        "review_note": "review fields are machine-proposed classifications for a human to confirm; "
        "they are not legal advice and not a citation_status",
        "acts": acts,
        "repealed_acts": repealed,
        "units": units,
        "requirements": requirements,
    }
    outputs[KNOWLEDGE / "legal_catalog.json"] = (
        json.dumps(catalog, ensure_ascii=False, indent=1) + "\n"
    )

    active = []
    for rule_id, rule in rulebook.rules.items():
        if not rule.enabled:
            continue
        norms = []
        for norm_id, strength in rule.norms.items():
            norm = rulebook.norms[norm_id]
            norms.append(
                {
                    "norm_id": norm_id,
                    "act": norm.act,
                    "document_id": SOURCES_META["acts"].get(norm.act, {}).get("document_id"),
                    "punkt": norm.punkt,
                    "quote": norm.quote,
                    "url": str(norm.url),
                    "legal_link_strength": strength,
                    "citation_status": norm.citation_status,
                    "source_check": checks[norm_id],
                }
            )
        source_ok = all(n["source_check"]["result"] == "quote_in_cited_unit" for n in norms)
        human_ok = all(n["citation_status"] == "verified" for n in norms)
        active.append(
            {
                "rule_id": rule_id,
                "type_ru": rule.type_ru,
                "requirement": rule.requirement,
                "visible_breach": rule.visible_breach,
                "not_visible": rule.not_visible,
                "primary_strength": next(iter(rule.norms.values())),
                "norms": norms,
                "f1": capabilities.get(rule_id),
                "status": "verified" if source_ok and human_ok else "needs_review",
                "needs_review_because": [
                    *(["a cited quote does not match the stored text"] if not source_ok else []),
                    *(
                        ["no human has marked the citations verified on adilet.zan.kz"]
                        if not human_ok
                        else []
                    ),
                ],
            }
        )
    outputs[KNOWLEDGE / "active_rules.json"] = (
        json.dumps(
            {"generated_by": "scripts/build_legal_catalog.py", "rules": active},
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )

    by_event: dict[str, list[str]] = {}
    for rule_id, capability in capabilities.items():
        for kind in capability["events"]:
            by_event.setdefault(kind, []).append(rule_id)
    mapping = {
        "generated_by": "scripts/build_legal_catalog.py (read from backend/f1/rules.py)",
        "note": "event kinds are what backend/f1/events.py emits; a rule's finding is the "
        "event_type "
        "the service reports. rulebook states_used are the older VLM-era vocabulary.",
        "rules": {
            rule_id: {
                **capability,
                "enabled": rulebook.rules[rule_id].enabled if rule_id in rulebook.rules else None,
                "norms": list(rulebook.rules[rule_id].norms) if rule_id in rulebook.rules else [],
                "catalog_units": sorted(
                    {
                        checks[n]["unit"]
                        for n in rulebook.rules[rule_id].norms
                        if checks[n].get("unit")
                    }
                )
                if rule_id in rulebook.rules
                else [],
                "rulebook_states_used": rulebook.rules[rule_id].states_used
                if rule_id in rulebook.rules
                else [],
            }
            for rule_id, capability in capabilities.items()
        },
        "events": {kind: sorted(rules) for kind, rules in sorted(by_event.items())},
        "rules_without_evaluator": sorted(set(rulebook.rules) - set(capabilities)),
    }
    outputs[KNOWLEDGE / "event_mapping.json"] = (
        json.dumps(mapping, ensure_ascii=False, indent=1) + "\n"
    )
    outputs[KNOWLEDGE / "legal_audit.md"] = audit(
        rulebook, acts, repealed, checks, punkts, review, active
    )
    outputs[KNOWLEDGE / "coverage_matrix.md"] = coverage(
        rulebook, requirements, capabilities, checks
    )
    return outputs


def _tests_naming(rule_id: str) -> list[str]:
    return sorted(
        path.name for path in TESTS.glob("test_*.py") if rule_id in path.read_text(encoding="utf-8")
    )


def coverage(rulebook, requirements, capabilities, checks) -> str:
    def cell(text: str) -> str:
        return str(text).replace("|", "/").replace("\n", " ")

    out = [
        "# Coverage matrix (generated by `scripts/build_legal_catalog.py`; do not edit)",
        "",
        "Requirements are derived from the law alone (`legal_requirements.yaml`, quotes "
        "machine-checked against `sources/`); decisions compare them with the rulebook and with "
        "what `backend/f1/rules.py` really reads (`event_mapping.json`). Machine-checked quotes "
        "are not human-verified interpretations: `citation_status` stays as the rulebook says.",
        "",
        "## Summary",
        "",
        "| item | in the law | in rulebook | model detects | decision |",
        "|---|---|---|---|---|",
    ]
    by_rule: dict[str, list[dict]] = {}
    for item in requirements:
        for rule_id in item["rules"]:
            by_rule.setdefault(rule_id, []).append(item)
    for rule_id, rule in rulebook.rules.items():
        found = by_rule.get(rule_id, [])
        law = "yes" if found else "not found independently"
        detects = "yes" if rule_id in capabilities else "no evaluator"
        decisions = sorted({i["decision"] for i in found}) or ["no supporting requirement"]
        state = "enabled" if rule.enabled else "disabled"
        out.append(f"| {rule_id} | {law} | yes ({state}) | {detects} | {', '.join(decisions)} |")
    for item in requirements:
        if item["rules"]:
            continue
        out.append(
            f"| {item['id']} | yes ({item['unit']}) | no | {item['model_support']} | "
            f"{item['decision']} |"
        )
    out += [
        "",
        "Decisions: " + "; ".join(f"`{k}` {v}" for k, v in DECISIONS.items()) + ".",
        "",
        "## Law -> system",
        "",
        "| requirement | unit | breach on video | needs | F1 reads (via rule) | rule | tests "
        "| decision | note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in requirements:
        reads = sorted(
            {kind for r in item["rules"] for kind in capabilities.get(r, {}).get("events", [])}
        )
        tests = sorted({name for r in item["rules"] for name in _tests_naming(r)})
        out.append(
            f"| {item['id']} | {item['unit']} | {cell(item['breach_visual'])} | "
            f"{', '.join(item['signals'])} | {', '.join(reads) or '-'} | "
            f"{', '.join(item['rules']) or '-'} | {', '.join(tests) or '-'} | "
            f"{item['decision']} | {cell(item['decision_note'])} |"
        )
    out += [
        "",
        "## System -> law",
        "",
        "| rule | enabled | rulebook norms (strength, source check) | requirements found "
        "independently | F1 evaluator | tests |",
        "|---|---|---|---|---|---|",
    ]
    for rule_id, rule in rulebook.rules.items():
        norms = ", ".join(f"{n} ({s}, {checks[n]['result']})" for n, s in rule.norms.items())
        found = ", ".join(i["id"] for i in by_rule.get(rule_id, [])) or "**none**"
        evaluator = capabilities.get(rule_id, {}).get("evaluator", "-")
        out.append(
            f"| {rule_id} | {rule.enabled} | {norms} | {found} | {evaluator} | "
            f"{', '.join(_tests_naming(rule_id)) or '-'} |"
        )
    return "\n".join(out) + "\n"


def audit(rulebook, acts, repealed, checks, punkts, review, active) -> str:
    out = [
        "# Legal audit (generated by `scripts/build_legal_catalog.py`; do not edit)",
        "",
        "Hand-written findings and decisions: `knowledge/README.md`, section *Source check*.",
        "",
        "## Sources",
        "",
        "| act | document | punkts | latest amendment in footnotes | status |",
        "|---|---|---|---|---|",
    ]
    for act, meta in acts.items():
        out.append(
            f"| {act} | [{meta['document_id']}]({meta['url']}) | {meta['punkts']} | "
            f"{meta['latest_amendment_in_footnotes'] or '-'} | {meta['status']} |"
        )
    for act, meta in repealed.items():
        out.append(
            f"| {act} | {meta['document_id']} | - | - | "
            f"repealed by {meta['repealed_by']}: never cite |"
        )
    out += [
        "",
        "## Rulebook norms against the stored text",
        "",
        "`quote_in_cited_unit` means the quote is verbatim (whitespace, case and dash style "
        "aside) in the punkt/part/subpunkt the rulebook cites. It is a machine check of the "
        "text, not the human "
        "`citation_status`.",
        "",
        "| norm | act | cited | check | detail |",
        "|---|---|---|---|---|",
    ]
    for norm_id, norm in rulebook.norms.items():
        check = checks[norm_id]
        out.append(
            f"| {norm_id} | {norm.act} | {norm.punkt} | {check['result']} | "
            f"{check.get('detail', check.get('unit', ''))} |"
        )
    out += [
        "",
        "## Enabled rules",
        "",
        "| rule | primary strength | norms | status |",
        "|---|---|---|---|",
    ]
    for rule in active:
        norms = ", ".join(
            f"{n['norm_id']} ({n['legal_link_strength']}, {n['source_check']['result']})"
            for n in rule["norms"]
        )
        out.append(
            f"| {rule['rule_id']} | {rule['primary_strength']} | {norms} | {rule['status']} |"
        )
    counts: dict[str, dict[str, int]] = {}
    for unit_id, entry in review.items():
        act = unit_id.split("-")[0]
        counts.setdefault(act, {}).setdefault(entry["status"], 0)
        counts[act][entry["status"]] += 1
    out += [
        "",
        "## Punkt review",
        "",
        "| act | punkts | reviewed | linked | candidate | weak | excluded |",
        "|---|---|---|---|---|---|---|",
    ]
    for act, meta in acts.items():
        c = counts.get(act, {})
        reviewed = sum(1 for p in punkts.values() if p.act == act and p.id in review)
        out.append(
            f"| {act} | {meta['punkts']} | {reviewed} | {c.get('linked', 0)} | "
            f"{c.get('candidate', 0)} | "
            f"{c.get('weak', 0)} | {c.get('excluded', 0)} |"
        )
    for status, title in (
        ("candidate", "Candidates (observable, no rule yet)"),
        ("weak", "Weak links"),
        ("linked", "Linked to rules"),
    ):
        rows = [(u, e) for u, e in review.items() if e["status"] == status]
        if rows:
            out += [
                "",
                f"### {title}",
                "",
                "| unit | observability | rules | reason |",
                "|---|---|---|---|",
            ]
            out += [
                f"| {u} | {e['observability']} | {', '.join(e.get('rules', [])) or '-'} | "
                f"{e['reason']} |"
                for u, e in rows
            ]
    excluded: dict[str, int] = {}
    for entry in review.values():
        if entry["status"] == "excluded":
            key = f"{entry['applicability']} / {entry['observability']}"
            excluded[key] = excluded.get(key, 0) + 1
    if excluded:
        out += [
            "",
            "### Excluded, by reason",
            "",
            "| applicability / observability | units |",
            "|---|---|",
        ]
        out += [f"| {k} | {v} |" for k, v in sorted(excluded.items(), key=lambda kv: -kv[1])]
    unreviewed = [p for p in punkts if p not in review]
    out += [
        "",
        f"Unreviewed punkts: {len(unreviewed)}"
        + (
            f" ({', '.join(unreviewed[:40])}{' ...' if len(unreviewed) > 40 else ''})"
            if unreviewed
            else ""
        ),
        "",
    ]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="fail if a generated file is stale")
    args = parser.parse_args()
    outputs = build()
    stale = [
        p for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text
    ]
    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    for path in stale:
        path.write_text(outputs[path], encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
