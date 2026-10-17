"""Unit tests for `eval.ground_truth` on synthetic workbooks only.

The cell shapes mirror the real sources (e.g. '57 секунда', '1минута 8 секунда', 'Пара: X-N'), but
every clip, time and text here is made up: this suite never reads organizer labels.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import openpyxl
import pytest

import eval.ground_truth as gtmod
from eval.ground_truth import (
    HumanAnnotation,
    HumanSheets,
    LabelFormatError,
    OrganizerLabel,
    Reviews,
    VideoFile,
    build_ground_truth,
    draw_split,
    find_discrepancies,
    parse_timecode,
    read_human_annotations,
    read_layouts,
    read_organizer_labels,
    read_reviews,
    split_problems,
)

ORG_HEADER = ("наименование файла", "таймстемп", "нарушение / без нарушения")
V_HEADER = (
    "№", "Ролик", "Секунда (метка)", "Кадр на метке", "Что видно на видео", "Тип нарушения",
    "Норма 1", "Ссылка 1", "Норма 2", "Ссылка 2", "Искать на странице (Ctrl+F)", "Уверенность",
    "Проверить вручную?", "Что проверить", "Пара без нарушения / файлы", "Ваша проверка",
)  # fmt: skip
C_HEADER = ("Ролик", "Что видно на видео", "Парный ролик с нарушением", "Лист кадров", "Видео")


def _workbook(path: Path, sheets: dict[str, list[tuple]]) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(list(row))
    wb.save(path)
    return path


def _organizer(path: Path, rows: list[tuple], header: tuple = ORG_HEADER) -> Path:
    return _workbook(path, {"labels": [header, *rows]})


def _v_row(clip, second, pair="Лист кадров", must_check="нет", link="Открыть п. 9 ч. 1"):
    row = [None] * len(V_HEADER)
    row[0], row[1], row[2], row[5] = 1, clip, second, "тип"
    row[7], row[11], row[12], row[14] = link, "высокая", must_check, pair
    return tuple(row)


def _human(path: Path, v_rows: list[tuple], c_rows: list[tuple]) -> Path:
    return _workbook(
        path,
        {
            "Нарушения": [
                ("Заголовок",),
                ("Как пользоваться",),
                V_HEADER,
                *v_rows,
                (None, "Итого роликов с нарушением:"),
            ],
            "Без нарушений": [C_HEADER, *c_rows],
        },
    )


# ---- timecodes --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("57 секунда", 57.0), ("1минута 8 секунда", 68.0), ("2 минуты 5 секунд", 125.0),
     (" 3 Секунды ", 3.0)],
)  # fmt: skip
def test_parse_timecode_real_shapes(cell, expected):
    assert parse_timecode(cell) == expected


@pytest.mark.parametrize("cell", ["57", "57 / 68", "1:08", "около 5 секунд", "", "секунда"])
def test_parse_timecode_rejects_unknown_shapes(cell):
    with pytest.raises(LabelFormatError):
        parse_timecode(cell)


# ---- organizer labels -------------------------------------------------------------------------


def test_read_organizer_labels(tmp_path):
    path = _organizer(
        tmp_path / "o.xlsx",
        [("Х-3", "7 секунда", "нарушение"), ("X-5", None, "без нарушения"),
         ("Х-9", "1минута 2 секунда", "Нарушение")],
    )  # fmt: skip
    assert read_organizer_labels(path) == {
        "X-3": OrganizerLabel(True, (7.0,)),
        "X-5": OrganizerLabel(False, ()),
        "X-9": OrganizerLabel(True, (62.0,)),
    }


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([("X-3", "7 секунда", "нарушено")], "unknown verdict"),
        ([("X-3", None, "нарушение")], "verdict and timecode disagree"),
        ([("X-3", "7 секунда", "без нарушения")], "verdict and timecode disagree"),
        ([("X-3", "7", "нарушение")], "unrecognised timecode"),
        ([("X-3", None, "без нарушения"), ("Х-3", None, "без нарушения")], "second label for X-3"),
        ([("итого", None, "без нарушения")], "not a clip ID"),
    ],
)
def test_read_organizer_labels_rejects_bad_rows(tmp_path, rows, message):
    with pytest.raises(LabelFormatError, match=message):
        read_organizer_labels(_organizer(tmp_path / "o.xlsx", rows))


def test_read_organizer_labels_checks_header(tmp_path):
    path = _organizer(tmp_path / "o.xlsx", [], header=("файл", "время", "вердикт"))
    with pytest.raises(LabelFormatError, match="unexpected header"):
        read_organizer_labels(path)


# ---- human annotations ------------------------------------------------------------------------


def test_read_human_annotations(tmp_path):
    path = _human(
        tmp_path / "h.xlsx",
        [_v_row("X-3", 7, pair="Пара: Х-5\nЛист кадров"), _v_row("X-3", None)],
        [("X-5", "ok", "X-3"), ("X-6", "ok", "X-3, X-4"), ("X-7", "ok", None)],
    )
    sheets = read_human_annotations(path)
    assert [(h.clip_id, h.times, h.norm1) for h in sheets.violations] == [
        # legacy: only a lower-case 'открыть' prefix is stripped; the scorer reads digits only
        ("X-3", (7.0,), "Открыть п. 9 ч. 1"),
        ("X-3", (), "Открыть п. 9 ч. 1"),
    ]
    assert sheets.clean == ["X-5", "X-6", "X-7"]
    assert sheets.pairs == [("X-3", "X-5"), ("X-5", "X-3"), ("X-6", "X-3"), ("X-6", "X-4")]


def test_read_human_annotations_strips_lower_case_link_prefix(tmp_path):
    path = _human(tmp_path / "h.xlsx", [_v_row("X-3", 7, link="открыть 231-20-2")], [])
    assert read_human_annotations(path).violations[0].norm1 == "231-20-2"


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (_v_row("X-3", "7"), "not a number"),
        (_v_row("итого", 7), "not a clip ID"),
    ],
)
def test_read_human_annotations_rejects_bad_rows(tmp_path, row, message):
    with pytest.raises(LabelFormatError, match=message):
        read_human_annotations(_human(tmp_path / "h.xlsx", [row], []))


def test_read_human_annotations_requires_named_columns(tmp_path):
    path = _workbook(
        tmp_path / "h.xlsx",
        {"Нарушения": [("t",), ("h",), ("№", "Ролик")], "Без нарушений": [C_HEADER]},
    )
    with pytest.raises(LabelFormatError, match="header lacks columns"):
        read_human_annotations(path)


def test_read_layouts_and_reviews(tmp_path):
    cases = _workbook(
        tmp_path / "c.xlsx",
        {"Clips": [("Clip", "Label", "Camera layout"), ("Х-3", "x", "Back"), ("X-5", "y", "Door")]},
    )
    assert read_layouts(cases) == {"X-3": "Back", "X-5": "Door"}
    reviews = tmp_path / "r.json"
    reviews.write_text(json.dumps({"human_annotation_unreliable": {"Х-3": "why"}}), "utf-8")
    assert read_reviews(reviews) == Reviews(unreliable={"X-3": "why"}, reviewed_ok={})
    reviews.write_text(json.dumps({"unreliable": ["X-3"]}), "utf-8")
    with pytest.raises(LabelFormatError, match="unknown keys"):
        read_reviews(reviews)


# ---- build ------------------------------------------------------------------------------------


def _ann(clip, *times, must_check="нет"):
    return HumanAnnotation(clip, tuple(times), "тип", "п. 9", "высокая", must_check, None)


def _videos(*specs):
    return [VideoFile(c, f"open/videos/{c}.mov", sha) for c, sha in specs]


def _build(videos, organizer, human, reviews=None, layouts=None):
    reviews = reviews or Reviews({}, {})
    layouts = layouts or {v.clip_id: "Back" for v in videos}
    return build_ground_truth(Path("/data"), videos, organizer, human, layouts, reviews)


def test_duplicates_become_one_video_and_keep_each_label():
    videos = _videos(("X-4", "a"), ("X-47", "a"), ("X-5", "b"))
    organizer = {
        "X-4": OrganizerLabel(True, (10.0,)),
        "X-47": OrganizerLabel(True, (12.0,)),
        "X-5": OrganizerLabel(False, ()),
    }
    human = HumanSheets([_ann("X-4", 11.0)], ["X-5"], [("X-4", "X-5")])
    gt = _build(videos, organizer, human)

    assert list(gt) == ["X-4", "X-5"]
    assert gt["X-4"]["dups"] == ["X-4", "X-47"]
    assert gt["X-4"]["org_times"] == [10.0, 12.0]
    assert gt["X-4"]["files"] == [
        {"clip_id": "X-4", "video": "open/videos/X-4.mov",
         "organizer": {"violation": True, "times": [10.0]}},
        {"clip_id": "X-47", "video": "open/videos/X-47.mov",
         "organizer": {"violation": True, "times": [12.0]}},
    ]  # fmt: skip
    assert gt["X-4"]["path"] == "/data/open/videos/X-4.mov"
    assert gt["X-4"]["group"] == gt["X-5"]["group"]  # matched pair
    kinds = [i["kind"] for i in find_discrepancies(gt, human, None)]
    assert kinds == ["duplicate_organizer_labels_differ"]


def test_reliability_follows_reviews_not_code():
    videos = _videos(("X-1", "a"), ("X-2", "b"), ("X-3", "c"))
    organizer = {c: OrganizerLabel(True, (5.0,)) for c in ("X-1", "X-2", "X-3")}
    human = HumanSheets(
        [_ann("X-1", 5.0), _ann("X-2", 5.0, must_check="ОБЯЗАТЕЛЬНО"),
         _ann("X-3", 5.0, must_check="ОБЯЗАТЕЛЬНО")],
        [],
        [],
    )  # fmt: skip
    reviews = Reviews(unreliable={"X-1": "unsure"}, reviewed_ok={"X-3": "agreed"})
    gt = _build(videos, organizer, human, reviews)
    assert [gt[c]["human_reliable"] for c in ("X-1", "X-2", "X-3")] == [False, False, True]


@pytest.mark.parametrize(
    ("human", "message"),
    [
        (HumanSheets([_ann("X-9", 1.0)], [], []), "no video"),
        (HumanSheets([], ["X-1"], [("X-1", "X-9")]), "no video"),
    ],
)
def test_build_rejects_clips_without_video(human, message):
    with pytest.raises(LabelFormatError, match=message):
        _build(_videos(("X-1", "a")), {"X-1": OrganizerLabel(False, ())}, human)


def test_build_requires_a_label_for_every_video():
    with pytest.raises(LabelFormatError, match="videos only"):
        _build(_videos(("X-1", "a"), ("X-2", "b")), {"X-1": OrganizerLabel(False, ())},
               HumanSheets([], [], []))  # fmt: skip


def test_discrepancies_are_reported_not_resolved():
    videos = _videos(("X-1", "a"), ("X-2", "b"), ("X-3", "c"))
    organizer = {
        "X-1": OrganizerLabel(True, (5.0,)),
        "X-2": OrganizerLabel(False, ()),
        "X-3": OrganizerLabel(True, (30.0,)),
    }
    human = HumanSheets([_ann("X-2", 3.0), _ann("X-3", 20.0)], ["X-3"], [])
    gt = json.loads(json.dumps(_build(videos, organizer, human)))
    previous = json.loads(json.dumps(gt))
    previous["X-1"]["human_reliable"] = True
    items = find_discrepancies(gt, human, previous)
    found = {(i["kind"], i["clip_id"]) for i in items}
    assert found == {
        ("organizer_violation_without_human_annotation", "X-1"),
        ("clip_on_no_human_sheet", "X-1"),
        ("human_annotation_on_organizer_clean_clip", "X-2"),
        ("human_clean_sheet_on_organizer_violation", "X-3"),
        ("organizer_time_far_from_human", "X-3"),
        ("changed_since_previous_gt", "X-1"),
    }
    gap = next(i for i in items if i["kind"] == "organizer_time_far_from_human")
    assert (gap["source_clip"], gap["nearest_gap_s"]) == ("X-3", 10.0)
    assert gt["X-1"]["human_reliable"] is False  # the report never edits the ground truth


# ---- split ------------------------------------------------------------------------------------


def _toy_gt(n=12):
    return {
        f"X-{i}": {"group": f"X-{i - i % 2}", "layout": "A" if i % 3 else "B"}
        for i in range(2, n + 2)
    }


def test_frozen_split_check():
    gt = _toy_gt()
    frozen = draw_split(gt)
    assert draw_split(gt) == frozen  # deterministic
    assert split_problems(gt, frozen) == []
    assert set(frozen.values()) == {"dev", "lockbox"}

    moved = dict(frozen)
    k = next(iter(moved))
    moved[k] = "dev" if moved[k] == "lockbox" else "lockbox"
    problems = split_problems(gt, moved)
    assert any("moves" in p for p in problems) and any("straddles" in p for p in problems)
    assert any("different clips" in p for p in split_problems(gt, {**frozen, "X-99": "dev"}))


# ---- CLI --------------------------------------------------------------------------------------


def test_main_reports_and_writes_only_when_asked(tmp_path, monkeypatch, capsys):
    root, out = tmp_path / "data", tmp_path / "out"
    (root / "open" / "videos").mkdir(parents=True)
    (root / "team").mkdir()
    for clip, content in (("X-1", b"one"), ("Х-2", b"two"), ("Х-3", b"one")):
        (root / "open" / "videos" / f"{clip}.mov").write_bytes(content)
    _organizer(
        root / "open" / "open_labels.xlsx",
        [("X-1", "5 секунда", "нарушение"), ("Х-2", None, "без нарушения"),
         ("Х-3", "6 секунда", "нарушение")],
    )  # fmt: skip
    _human(root / "team" / "Таблица_нарушений.xlsx", [_v_row("X-1", 5, pair="Пара: X-2")], [
        ("X-2", "ok", "X-1")])  # fmt: skip
    _workbook(
        root / "team" / "Cash_Discipline_Cases_Rules.xlsx",
        {"Clips": [("Clip", "Camera layout"), ("X-1", "A"), ("X-2", "A"), ("X-3", "A")]},
    )
    (root / "team" / "reviews.json").write_text("{}", "utf-8")
    manifest = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }
    monkeypatch.setenv("DATATHON_DATA_ROOT", str(root))
    monkeypatch.setattr(gtmod, "load_manifest", lambda: manifest)

    out.mkdir()
    (out / "split.json").write_text(json.dumps({"X-1": "dev", "X-2": "dev"}), "utf-8")
    assert gtmod.main(["--out", str(out)]) == 0
    assert not (out / "gt.json").exists()
    report = json.loads((out / "discrepancies.json").read_text("utf-8"))
    assert [i["kind"] for i in report["items"]] == ["duplicate_organizer_labels_differ"]
    assert "frozen split reproduced" in capsys.readouterr().out

    assert gtmod.main(["--out", str(out), "--write"]) == 0
    gt = json.loads((out / "gt.json").read_text("utf-8"))
    assert list(gt) == ["X-1", "X-2"] and gt["X-1"]["dups"] == ["X-1", "X-3"]
    assert json.loads((out / "split.json").read_text("utf-8")) == {"X-1": "dev", "X-2": "dev"}

    (root / "open" / "videos" / "X-1.mov").write_bytes(b"changed")
    assert gtmod.main(["--out", str(out)]) == 1  # data no longer matches the manifest
