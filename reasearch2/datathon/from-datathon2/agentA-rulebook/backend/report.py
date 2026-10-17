import csv
import html
import json
from copy import deepcopy
from pathlib import Path

from backend.codex import Codex
from backend.evaluation import match_events, score


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_reports(
    out: Path, rows: list[dict], summaries: list[dict], codex: Codex | None = None
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_csv(
        out / "summary.csv", [{k: v for k, v in s.items() if k != "per_rule"} for s in summaries]
    )
    write_csv(
        out / "per_rule.csv",
        [
            {"scope": summary["scope"], "rule_id": rule_id, **counts}
            for summary in summaries
            for rule_id, counts in summary["per_rule"].items()
        ],
    )
    write_csv(
        out / "per_video.csv",
        [
            {
                "aliases": ";".join(row["aliases"]),
                "file": row["file"],
                "checksum": row["checksum"],
                "split": row["split"],
                "layouts": ";".join(row["layouts"]),
                "status": row["status"],
                "label_times_sec": json.dumps([e["timestamp_sec"] for e in row["labels"]]),
                "prediction_times_sec": json.dumps(
                    [v["timecode_sec"] for v in row["result"]["violations"]]
                )
                if row["result"]
                else "[]",
                "verdict": row["result"]["verdict"] if row["result"] else "failed",
                "analysis_stage": row["result"]["analysis_stage"] if row["result"] else "",
                "sample_fps": row["result"]["video"]["sample_fps"] if row["result"] else "",
                "perception_cached": row["result"].get("perception_cached", False)
                if row["result"]
                else False,
                "coverage": json.dumps(row["result"].get("coverage", {}))
                if row["result"]
                else "{}",
                "runtime_sec": row["result"]["runtime_sec"] if row["result"] else "",
                "end_to_end_sec": row["end_to_end_sec"],
                "error": row["error"],
            }
            for row in rows
        ],
    )
    (out / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    escape = lambda value: html.escape(str(value), quote=True)  # noqa: E731
    parts = [
        """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forte — оценка</title><style>
body{font:16px system-ui;max-width:1120px;margin:32px auto;padding:0 20px;
background:#f5f4f1;color:#222}
article{background:white;padding:24px;margin:24px 0;border:1px solid #ccc}
table{border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #bbb}
.warning{background:#fff2cd;padding:16px}
img{max-height:400px;max-width:100%}video{max-width:100%;max-height:500px}svg{width:100%;height:64px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#713153}
</style><h1>Проверка кассовой дисциплины · оценка</h1>
<p class="warning">Локальные модели и детерминированные правила v1. Результаты предназначены
для проверки человеком. Изучите покрытие и предупреждения: неразборчивое состояние не считается
доказательством отсутствия нарушения.
Частота кадров и использование кеша указаны в per_video.csv.</p>
<p>SHA-256: одинаковые видео запускаются один раз; метки объединены. all_unique — уникальные видео;
all_clips — повторное взвешивание объединённых меток по исходным файлам.
held_out — целиком исключённый ракурс; одинаковый файл не попадает в оба сплита.
Сейчас это диагностический срез, не независимая проверка после настройки порогов.</p>
<table><tr><th>Срез</th><th>Видео</th><th>Accuracy</th><th>Recall</th><th>FAR</th>
<th>События ±2 с</th><th>Макс., с</th></tr>"""
    ]
    for summary in summaries:
        values = [
            summary[key]
            for key in (
                "scope",
                "scored_videos",
                "accuracy",
                "recall",
                "false_alarm_rate",
                "hits_2s",
                "slowest_sec",
            )
        ]
        parts.append("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in values) + "</tr>")
    parts.append(
        "</table><p><a href='per_rule.csv'>По правилам (CSV)</a> · "
        "<a href='results.json'>Полные результаты и события (JSON)</a></p>"
    )
    for row in rows:
        result = row["result"]
        parts.append(
            f"<article><h2>{escape(' / '.join(row['aliases']))}</h2>"
            f"<p>{escape(row['split'])} · {escape(row['layouts'])} · "
            f"{row['end_to_end_sec']:.2f} с</p>"
            f"<p>Метки: {escape(row['labels'])}</p>"
        )
        if result:
            parts.append(f"<p>Прогноз: {escape(result['verdict'])}</p>")
            for warning in result["warnings"]:
                parts.append(f"<p class='warning'>{escape(warning)}</p>")
            duration = result["video"]["duration_sec"]
            parts.append(
                '<svg viewBox="0 0 1000 64" role="img" aria-label="Журнал событий">'
                '<line x1="0" y1="32" x2="1000" y2="32" stroke="#aaa"/>'
            )
            for event in result["events"]:
                x = event["timestamp_sec"] / duration * 1000
                parts.append(
                    f'<circle cx="{x:.3f}" cy="32" r="2" fill="#777"><title>'
                    f"{escape(event)}</title></circle>"
                )
            for event in row["labels"]:
                x = event["timestamp_sec"] / duration * 1000
                parts.append(
                    f'<line x1="{x}" x2="{x}" y1="8" y2="56" stroke="#b51b47">'
                    f"<title>Метка {escape(event)}</title></line>"
                )
            for violation in result["violations"]:
                x = violation["timecode_sec"] / duration * 1000
                parts.append(
                    f'<line x1="{x}" x2="{x}" y1="16" y2="48" stroke="#238949">'
                    f"<title>{escape(violation['rule_id'])}</title></line>"
                )
            parts.append(
                "</svg><p>Серые точки: события; красные линии: метки; зеленые: прогнозы.</p>"
            )
            for violation in result["violations"]:
                parts.append(
                    f"<h3>{escape(violation['type'])} · {violation['timecode_sec']:.2f} с</h3>"
                    f"<p>{escape(violation['description'])}</p>"
                    f"<p>{escape(violation['rule_id'])} — "
                    f"<a href='{escape(violation['source_url'])}'>"
                    f"{escape(violation['source'])}</a></p>"
                )
                for frame in violation["evidence_frames"]:
                    parts.append(
                        f"<figure><img src='data:image/jpeg;base64,{frame['image_base64']}' "
                        f"alt='Кадр {frame['timestamp_sec']:.2f} с'>"
                        f"<figcaption>{frame['timestamp_sec']:.2f} с</figcaption></figure>"
                    )
            if row["debug_path"]:
                parts.append(
                    f"<video controls preload='none' src='{escape(row['debug_path'])}'></video>"
                )
            parts.append(
                f"<details><summary>Журнал событий ({len(result['events'])})</summary>"
                f"<pre>{escape(json.dumps(result['events'], ensure_ascii=False, indent=2))}"
                "</pre></details>"
            )
        else:
            parts.append(f"<p class='warning'>Ошибка: {escape(row['error'])}</p>")
        parts.append("</article>")
    parts.append("</html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")
    misses = []
    for row in rows:
        predicted = row["result"]["violations"] if row["result"] else []
        matches = match_events(
            [e["timestamp_sec"] for e in row["labels"]], [v["timecode_sec"] for v in predicted], 2
        )
        hit_indices = {pair[0] for pair in matches}
        for index, event in enumerate(row["labels"]):
            if index not in hit_indices:
                misses.append(
                    {
                        "clips": row["aliases"],
                        **event,
                        "reason": row["error"]
                        or "; ".join(row["result"]["warnings"])
                        or "No prediction within ±2 seconds; inspect event log and debug video",
                    }
                )
    (out / "misses.json").write_text(
        json.dumps(misses, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if codex is not None:
        write_rule_diagnostics(out, rows, codex)


def write_rule_diagnostics(out: Path, rows: list[dict], codex: Codex) -> None:
    from backend.rules import RULES

    incremental = []
    enabled = set()
    for rule_id in RULES:
        enabled.add(rule_id)
        # shortcut: independent rule functions have no effects on perception or each other.
        filtered = deepcopy(rows)
        for row in filtered:
            if row["result"]:
                row["result"]["violations"] = [
                    v for v in row["result"]["violations"] if v["rule_id"] in enabled
                ]
        for scope, subset in [
            ("all_unique", filtered),
            ("held_out", [r for r in filtered if r["split"] == "held_out"]),
        ]:
            metrics = score(subset, codex, scope)
            incremental.append(
                {
                    "added_rule": rule_id,
                    "enabled_rules": len(enabled),
                    **{
                        name: metrics[name]
                        for name in (
                            "scope",
                            "scored_videos",
                            "accuracy",
                            "recall",
                            "false_alarm_rate",
                            "hits_1s",
                            "hits_2s",
                            "hits_5s",
                        )
                    },
                }
            )
    write_csv(out / "incremental_rules.csv", incremental)
    metadata = {clip.id: clip for clip in codex.clips}
    pairs = []
    for positive in rows:
        if not positive["labels"]:
            continue
        cases = {metadata[alias].case_id for alias in positive["aliases"] if alias in metadata}
        for negative in rows:
            if negative["labels"]:
                continue
            correct_cases = {
                metadata[alias].case_id for alias in negative["aliases"] if alias in metadata
            }
            shared = cases & correct_cases - {None}
            if shared:
                pairs.append(
                    {
                        "case_ids": ";".join(sorted(shared)),
                        "violation_clips": ";".join(positive["aliases"]),
                        "correct_clips": ";".join(negative["aliases"]),
                        "violation_detected": bool(
                            positive["result"] and positive["result"]["violations"]
                        ),
                        "correct_false_alarm": bool(
                            negative["result"] and negative["result"]["violations"]
                        ),
                        "split": positive["split"],
                    }
                )
    if pairs:
        write_csv(out / "pairs.csv", pairs)
