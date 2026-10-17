"""Build the private ground-truth file (`gt.json`) from the team data root, report discrepancies,
and check that the frozen dev/lockbox split still follows from it.

The only code that reads organizer labels or human annotations (`backend/` never does). Sources
stay separate (GLOSSARY.md):
  organizer labels   open/open_labels.xlsx            -> verdict + timecodes (the ground truth)
  human annotations  team/Таблица_нарушений.xlsx      -> event times, type, cited norm, review
  team workbook      team/Cash_Discipline_Cases_Rules.xlsx -> camera layout per clip
  reviewer decisions team/reviews.json                -> which human annotations are unreliable

One `gt.json` entry per unique video (by SHA-256), keyed by its lowest clip ID. `files` keeps each
duplicate clip's own organizer label; `org_times` and `violation` are their union, as before.

Never prints label values: only counts and clip IDs. Discrepancies go to
`<out>/discrepancies.json` for people to review; nothing here changes a reviewer decision, and
`split.json` is never written.

Usage:
    .venv/bin/python -m eval.ground_truth            # build in memory, report, check the split
    .venv/bin/python -m eval.ground_truth --write    # also (over)write <out>/gt.json
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from backend.clip_id import InvalidClipId, clip_number, parse_clip_id
from eval.data import (
    CASES_WORKBOOK,
    HUMAN_ANNOTATIONS,
    ORGANIZER_LABELS,
    REPO_ROOT,
    REVIEWS,
    VIDEOS_DIR,
    check_data_root,
    data_root,
    load_manifest,
)

DEFAULT_OUT = REPO_ROOT / "reasearch1" / "validation-private"
TIME_GAP_S = 3.0
SPLIT_SEED = 26


class LabelFormatError(ValueError):
    """A source file does not have the shape this builder knows how to read."""


# ---- timecodes --------------------------------------------------------------------------------

_TIMECODE = re.compile(r"(?:(\d+)\s*минут[а-я]*\s*)?(\d+)\s*секунд[а-я]*")


def parse_timecode(cell: str) -> float:
    """'57 секунда' -> 57.0; '1минута 8 секунда' -> 68.0. Any other shape is an error."""
    match = _TIMECODE.fullmatch(cell.strip().lower())
    if not match:
        raise LabelFormatError("unrecognised timecode format")
    return float(int(match[1] or 0) * 60 + int(match[2]))


# ---- source readers ---------------------------------------------------------------------------

ORGANIZER_HEADER = ("наименование файла", "таймстемп", "нарушение / без нарушения")
ORGANIZER_VERDICTS = {"нарушение": True, "без нарушения": False}


@dataclass(frozen=True)
class OrganizerLabel:
    violation: bool
    times: tuple[float, ...]


@dataclass(frozen=True)
class HumanAnnotation:
    clip_id: str
    times: tuple[float, ...]
    type: str | None
    norm1: str | None
    confidence: str | None
    must_check: str | None
    review: str | None

    def as_json(self) -> dict:
        return {
            "times": list(self.times),
            "type": self.type,
            "norm1": self.norm1,
            "confidence": self.confidence,
            "must_check": self.must_check,
            "review": self.review,
        }


@dataclass(frozen=True)
class HumanSheets:
    violations: list[HumanAnnotation]  # 'Нарушения' rows, in sheet order
    clean: list[str]  # clip IDs on 'Без нарушений', in sheet order
    pairs: list[tuple[str, str]]  # (clip, its matched counterpart), violations sheet first


@dataclass(frozen=True)
class Reviews:
    unreliable: dict[str, str]  # clip ID -> why its human annotation is not reliable
    reviewed_ok: dict[str, str]  # clip ID -> must-check annotation re-reviewed and agreed


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _rows(path: Path, sheet: str | None = None) -> list[tuple]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = workbook[sheet] if sheet else workbook.worksheets[0]
        return [r for r in ws.iter_rows(values_only=True) if not all(_is_blank(v) for v in r)]
    except KeyError as exc:
        raise LabelFormatError(f"{path.name}: no sheet {sheet!r}") from exc
    finally:
        workbook.close()


def _columns(header: Sequence, required: Iterable[str], where: str) -> dict[str, int]:
    names = [str(v).strip() if v is not None else "" for v in header]
    missing = [name for name in required if name not in names]
    if missing:
        raise LabelFormatError(f"{where}: header lacks columns {missing}")
    return {name: names.index(name) for name in required}


def _text(value: object) -> str | None:
    return None if _is_blank(value) else str(value).strip()


def _clip_refs(cell: object) -> list[str]:
    return [parse_clip_id(m) for m in re.findall(r"[XХxх]\s*-\s*\d+", str(cell or ""))]


def read_organizer_labels(path: Path) -> dict[str, OrganizerLabel]:
    rows = _rows(path)
    header = tuple(str(v).strip().lower() if v is not None else "" for v in rows[0])
    if header[:3] != ORGANIZER_HEADER:
        raise LabelFormatError(f"{path.name}: unexpected header (want {ORGANIZER_HEADER})")
    labels: dict[str, OrganizerLabel] = {}
    for n, row in enumerate(rows[1:], start=2):
        where = f"{path.name} row {n}"
        try:
            clip = parse_clip_id(str(row[0]))
        except InvalidClipId as exc:
            raise LabelFormatError(f"{where}: first column is not a clip ID") from exc
        if clip in labels:
            raise LabelFormatError(f"{where}: second label for {clip}")
        verdict = str(row[2]).strip().lower() if len(row) > 2 and row[2] is not None else ""
        if verdict not in ORGANIZER_VERDICTS:
            raise LabelFormatError(f"{where}: unknown verdict")
        if _is_blank(row[1]):
            times: tuple[float, ...] = ()
        else:
            try:
                times = (parse_timecode(str(row[1])),)
            except LabelFormatError as exc:
                raise LabelFormatError(f"{where}: {exc}") from exc
        if ORGANIZER_VERDICTS[verdict] != bool(times):
            raise LabelFormatError(f"{where}: verdict and timecode disagree")
        labels[clip] = OrganizerLabel(violation=ORGANIZER_VERDICTS[verdict], times=times)
    return labels


VIOLATIONS_SHEET = "Нарушения"
CLEAN_SHEET = "Без нарушений"
_V_COLS = (
    "Ролик",
    "Секунда (метка)",
    "Тип нарушения",
    "Ссылка 1",
    "Уверенность",
    "Проверить вручную?",
    "Пара без нарушения / файлы",
    "Ваша проверка",
)
_C_COLS = ("Ролик", "Парный ролик с нарушением")


def read_human_annotations(path: Path) -> HumanSheets:
    # 'Нарушения': title row, how-to row, header row, then one row per annotated event and a
    # short footer of totals (rows with only the first column filled).
    rows = _rows(path, VIOLATIONS_SHEET)
    if len(rows) < 3:
        raise LabelFormatError(f"{path.name}/{VIOLATIONS_SHEET}: no header row")
    col = _columns(rows[2], _V_COLS, f"{path.name}/{VIOLATIONS_SHEET}")
    violations, pairs = [], []
    for n, row in enumerate(rows[3:], start=4):
        where = f"{path.name}/{VIOLATIONS_SHEET} non-empty row {n}"
        try:
            clip = parse_clip_id(str(row[col["Ролик"]]))
        except InvalidClipId as exc:
            if sum(not _is_blank(v) for v in row) == 1:
                continue  # footer note
            raise LabelFormatError(f"{where}: 'Ролик' is not a clip ID") from exc
        second = row[col["Секунда (метка)"]]
        if second is None:
            times: tuple[float, ...] = ()
        elif isinstance(second, int | float) and not isinstance(second, bool):
            times = (float(second),)
        else:
            raise LabelFormatError(f"{where}: 'Секунда (метка)' is not a number")
        link = str(row[col["Ссылка 1"]] or "")
        violations.append(
            HumanAnnotation(
                clip_id=clip,
                times=times,
                type=_text(row[col["Тип нарушения"]]),
                norm1=re.sub(r"^открыть\s*", "", link).strip() or None,
                confidence=_text(row[col["Уверенность"]]),
                must_check=_text(row[col["Проверить вручную?"]]),
                review=_text(row[col["Ваша проверка"]]),
            )
        )
        pairs += [(clip, other) for other in _clip_refs(row[col["Пара без нарушения / файлы"]])]

    rows = _rows(path, CLEAN_SHEET)
    col = _columns(rows[0], _C_COLS, f"{path.name}/{CLEAN_SHEET}")
    clean = []
    for n, row in enumerate(rows[1:], start=2):
        try:
            clip = parse_clip_id(str(row[col["Ролик"]]))
        except InvalidClipId as exc:
            raise LabelFormatError(f"{path.name}/{CLEAN_SHEET} row {n}: not a clip ID") from exc
        clean.append(clip)
        pairs += [(clip, other) for other in _clip_refs(row[col["Парный ролик с нарушением"]])]
    return HumanSheets(violations=violations, clean=clean, pairs=pairs)


def read_layouts(path: Path) -> dict[str, str]:
    rows = _rows(path, "Clips")
    col = _columns(rows[0], ("Clip", "Camera layout"), f"{path.name}/Clips")
    layouts = {}
    for n, row in enumerate(rows[1:], start=2):
        try:
            clip = parse_clip_id(str(row[col["Clip"]]))
        except InvalidClipId as exc:
            raise LabelFormatError(f"{path.name}/Clips row {n}: not a clip ID") from exc
        layout = _text(row[col["Camera layout"]])
        if layout is None:
            raise LabelFormatError(f"{path.name}/Clips row {n}: no camera layout")
        layouts[clip] = layout
    return layouts


def read_reviews(path: Path) -> Reviews:
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {"about", "human_annotation_unreliable", "must_check_reviewed_ok"}
    if unknown := set(data) - known:
        raise LabelFormatError(f"{path.name}: unknown keys {sorted(unknown)}")

    def clip_map(key: str) -> dict[str, str]:
        raw = data.get(key, {})
        if not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values()):
            raise LabelFormatError(f"{path.name}: {key} must map clip IDs to reasons")
        return {parse_clip_id(k): v for k, v in raw.items()}

    return Reviews(
        unreliable=clip_map("human_annotation_unreliable"),
        reviewed_ok=clip_map("must_check_reviewed_ok"),
    )


# ---- build ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class VideoFile:
    clip_id: str
    rel_path: str  # relative to the data root
    sha256: str


def video_files(root: Path, manifest: dict[str, str]) -> list[VideoFile]:
    files = []
    for rel, digest in manifest.items():
        if rel.startswith(f"{VIDEOS_DIR}/"):
            files.append(VideoFile(parse_clip_id(Path(rel).name), rel, digest))
    if len({f.clip_id for f in files}) != len(files):
        raise LabelFormatError("two video files share one clip ID")
    return sorted(files, key=lambda f: clip_number(f.clip_id))


def build_ground_truth(
    root: Path,
    videos: list[VideoFile],
    organizer: dict[str, OrganizerLabel],
    human: HumanSheets,
    layouts: dict[str, str],
    reviews: Reviews,
) -> dict[str, dict]:
    clip_ids = {v.clip_id for v in videos}
    if set(organizer) != clip_ids:
        raise LabelFormatError(
            f"organizer labels and videos differ: labels only {sorted(set(organizer) - clip_ids)}, "
            f"videos only {sorted(clip_ids - set(organizer))}"
        )
    unknown = {h.clip_id for h in human.violations} | set(human.clean) | set(layouts)
    unknown |= set(reviews.unreliable) | set(reviews.reviewed_ok)
    unknown |= {c for pair in human.pairs for c in pair}
    if unknown - clip_ids:
        raise LabelFormatError(f"sources name clips with no video: {sorted(unknown - clip_ids)}")
    if missing := clip_ids - set(layouts):
        raise LabelFormatError(f"no camera layout for {sorted(missing)}")

    # Duplicates: identical bytes -> one video, keyed by its lowest clip ID.
    by_hash: dict[str, list[VideoFile]] = collections.defaultdict(list)
    for v in videos:  # already in clip-number order
        by_hash[v.sha256].append(v)
    canon = {f.clip_id: group[0].clip_id for group in by_hash.values() for f in group}

    # Groups: union-find over duplicates and violation/clean pairs, in sheet order (the frozen
    # split was drawn from these exact group IDs, so the union order must not change).
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in human.pairs:
        root_b = find(canon[b])
        parent[find(canon[a])] = root_b

    annotations = collections.defaultdict(list)
    for h in human.violations:
        annotations[h.clip_id].append(h)

    gt = {}
    for group in by_hash.values():
        key = group[0].clip_id
        dups = [f.clip_id for f in group]
        rows = [h for d in dups for h in annotations[d]]
        reliable = (
            bool(rows)
            and not set(dups) & set(reviews.unreliable)
            and all(
                h.must_check != "ОБЯЗАТЕЛЬНО" or bool(set(dups) & set(reviews.reviewed_ok))
                for h in rows
            )
        )
        gt[key] = {
            "path": str(root / group[0].rel_path),
            "dups": dups,
            "violation": any(organizer[d].violation for d in dups),
            "org_times": sorted({t for d in dups for t in organizer[d].times}),
            "human": [h.as_json() for h in rows],
            "human_reliable": reliable,
            "layout": layouts[key],
            "group": find(key),
            "sha256": group[0].sha256,
            "files": [
                {
                    "clip_id": f.clip_id,
                    "video": f.rel_path,
                    "organizer": {
                        "violation": organizer[f.clip_id].violation,
                        "times": list(organizer[f.clip_id].times),
                    },
                }
                for f in group
            ],
        }
    return dict(sorted(gt.items(), key=lambda kv: clip_number(kv[0])))


# ---- split ------------------------------------------------------------------------------------


def draw_split(gt: dict[str, dict], seed: int = SPLIT_SEED) -> dict[str, str]:
    """The algorithm the frozen split was drawn with: whole groups, stratified by camera layout,
    about a third of each layout's groups to the lockbox. Used only to check the frozen split."""
    groups = collections.defaultdict(list)
    for k, c in gt.items():
        groups[c["group"]].append(k)
    rng = random.Random(seed)
    lock: set[str] = set()
    by_layout = collections.defaultdict(list)
    for g, ks in sorted(groups.items()):
        by_layout[collections.Counter(gt[k]["layout"] for k in ks).most_common(1)[0][0]].append(g)
    for _, gs in sorted(by_layout.items()):
        rng.shuffle(gs)
        for g in gs[: round(len(gs) / 3)]:
            lock.update(groups[g])
    return {k: ("lockbox" if k in lock else "dev") for k in gt}


def split_problems(gt: dict[str, dict], frozen: dict[str, str]) -> list[str]:
    """Why the frozen split no longer follows from `gt`; empty when it does."""
    problems = []
    if set(frozen) != set(gt):
        problems.append(
            f"split covers different clips: split only {sorted(set(frozen) - set(gt))}, "
            f"gt only {sorted(set(gt) - set(frozen))}"
        )
    redrawn = draw_split(gt)
    if moved := sorted(k for k in set(frozen) & set(redrawn) if frozen[k] != redrawn[k]):
        problems.append(f"redrawing the split moves {moved}")
    for g in {c["group"] for c in gt.values()}:
        sides = {frozen.get(k) for k, c in gt.items() if c["group"] == g}
        if len(sides) > 1:
            problems.append(f"group {g} straddles the split")
    return problems


# ---- discrepancies ----------------------------------------------------------------------------

_COMPARED_FIELDS = ("dups", "violation", "org_times", "human", "human_reliable", "layout", "group")


def find_discrepancies(
    gt: dict[str, dict], human: HumanSheets, previous: dict[str, dict] | None
) -> list[dict]:
    """Disagreements for people to review. Nothing here is resolved automatically."""
    items = []

    def add(kind: str, clip: str, **detail) -> None:
        items.append({"kind": kind, "clip_id": clip, **detail})

    clean_sheet = set(human.clean)
    violation_sheet = {h.clip_id for h in human.violations}
    for key, c in gt.items():
        dups = set(c["dups"])
        if c["violation"] and not c["human"]:
            add("organizer_violation_without_human_annotation", key)
        if not c["violation"] and c["human"]:
            add("human_annotation_on_organizer_clean_clip", key)
        if c["violation"] and dups & clean_sheet:
            add("human_clean_sheet_on_organizer_violation", key)
        if not dups & (clean_sheet | violation_sheet):
            add("clip_on_no_human_sheet", key)
        human_times = [t for h in c["human"] for t in h["times"]]
        if c["human"]:
            for f in c["files"]:
                for t in f["organizer"]["times"]:
                    gap = min((abs(t - x) for x in human_times), default=None)
                    if gap is None or gap > TIME_GAP_S:
                        add(
                            "organizer_time_far_from_human",
                            key,
                            source_clip=f["clip_id"],
                            organizer_time=t,
                            nearest_gap_s=gap,
                        )
        labels = {(f["organizer"]["violation"], tuple(f["organizer"]["times"])) for f in c["files"]}
        if len(labels) > 1:
            add(
                "duplicate_organizer_labels_differ",
                key,
                files={f["clip_id"]: f["organizer"] for f in c["files"]},
            )

    if previous is not None:
        for key in sorted(set(previous) | set(gt), key=clip_number):
            if key not in gt or key not in previous:
                add("clip_added_or_removed_since_previous_gt", key, in_new=key in gt)
                continue
            changed = [f for f in _COMPARED_FIELDS if previous[key].get(f) != gt[key][f]]
            if changed:
                add(
                    "changed_since_previous_gt",
                    key,
                    fields={
                        f: {"previous": previous[key].get(f), "new": gt[key][f]} for f in changed
                    },
                )
    return items


# ---- CLI --------------------------------------------------------------------------------------


def load_sources(root: Path, manifest: dict[str, str]):
    return (
        video_files(root, manifest),
        read_organizer_labels(root / ORGANIZER_LABELS),
        read_human_annotations(root / HUMAN_ANNOTATIONS),
        read_layouts(root / CASES_WORKBOOK),
        read_reviews(root / REVIEWS),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--write", action="store_true", help="write <out>/gt.json")
    args = ap.parse_args(argv)

    root, manifest = data_root(), load_manifest()
    check = check_data_root(root, manifest)
    if not check.ok:
        print(
            f"data root {root} does not match the manifest: {len(check.missing)} missing, "
            f"{len(check.mismatched)} mismatched, {len(check.unlisted)} unlisted "
            "(run `python -m eval.sync_data` for details)",
            file=sys.stderr,
        )
        return 1

    videos, organizer, human, layouts, reviews = load_sources(root, manifest)
    gt = build_ground_truth(root, videos, organizer, human, layouts, reviews)
    gt = json.loads(json.dumps(gt, ensure_ascii=False))  # compare in the form that is written

    gt_path, split_path = args.out / "gt.json", args.out / "split.json"
    previous = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else None
    items = find_discrepancies(gt, human, previous)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "discrepancies.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    viol = sum(c["violation"] for c in gt.values())
    print(
        f"files {len(videos)} | unique videos {len(gt)} | violation {viol} | "
        f"clean {len(gt) - viol} | duplicate files {len(videos) - len(gt)}"
    )
    print(
        f"human annotation rows {len(human.violations)} | clean-sheet clips {len(human.clean)} | "
        f"reliable violation videos "
        f"{sum(c['violation'] and c['human_reliable'] for c in gt.values())}"
    )
    print(f"discrepancies -> {args.out / 'discrepancies.json'}:")
    for kind, n in sorted(collections.Counter(i["kind"] for i in items).items()):
        clips = sorted({i["clip_id"] for i in items if i["kind"] == kind}, key=clip_number)
        print(f"  {kind}: {n} ({', '.join(clips)})")

    ok = True
    if not split_path.exists():
        print(f"split: {split_path} missing", file=sys.stderr)
        ok = False
    else:
        problems = split_problems(gt, json.loads(split_path.read_text(encoding="utf-8")))
        print("split: frozen split reproduced" if not problems else "split: MISMATCH")
        for p in problems:
            print(f"  {p}")
        ok &= not problems

    if args.write:
        gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {gt_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
