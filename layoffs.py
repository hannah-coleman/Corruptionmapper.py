"""Layoff log and pattern checks against records the user supplies.

The log holds layoff events, job postings and payroll headcounts, each citing a saved record. The
checks show timing and count patterns only. They cannot show who was chosen or why, so every flag
lists ordinary explanations and the next record to request.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

WARN_NOTICE_DAYS = 60
AGGREGATION_DAYS = 90
AGGREGATION_THRESHOLD = 50
REHIRE_DAYS = 180
HEADCOUNT_TOLERANCE = 0.25
KINDS = {"events": ("employer", "date", "count", "source"), "postings": ("employer", "title", "date", "source"), "headcounts": ("employer", "period_end", "headcount", "source")}
OPTIONAL = {"events": ("notice_date", "kind", "stated_reason", "positions", "note", "source_date"), "postings": ("note", "source_date"), "headcounts": ("note", "source_date")}
MAX_ROWS = 5000


def _day(value: str, label: str) -> str:
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as error:
        raise ValueError(f"{label} must be a date like 2026-03-31.") from error


def _count(value, label: str) -> int:
    try:
        number = int(str(value).strip())
    except ValueError as error:
        raise ValueError(f"{label} must be a whole number.") from error
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number


def load(path: Path | str) -> dict:
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    except json.JSONDecodeError:
        data = {}
    return {name: data.get(name, []) if isinstance(data, dict) else [] for name in KINDS}


def _clean(table: str, row: dict) -> dict:
    if table not in KINDS:
        raise ValueError("Unknown table.")
    for field in KINDS[table]:
        if not str(row.get(field, "")).strip():
            raise ValueError(f"'{field}' is required (every entry must cite its source).")
    item = {field: str(row.get(field, "")).strip() for field in KINDS[table] + OPTIONAL[table]}
    for field in ("date", "period_end", "notice_date"):
        if item.get(field):
            item[field] = _day(item[field], field)
    for field in ("count", "headcount"):
        if field in item:
            item[field] = _count(item[field], field)
    return item


def add(path: Path | str, table: str, row: dict) -> dict:
    item = _clean(table, row)
    item["id"] = str(uuid4())
    data = load(path)
    data[table].append(item)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return item


def import_csv(path: Path | str, table: str, text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Import at most {MAX_ROWS} rows at a time.")
    good, errors = [], []
    for number, row in enumerate(rows, start=2):
        try:
            good.append(_clean(table, {(k or "").strip().lower(): v for k, v in row.items()}))
        except ValueError as error:
            errors.append(f"Row {number}: {error}")
    data = load(path)
    for item in good:
        item["id"] = str(uuid4())
    data[table] += good
    if good:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"added": len(good), "errors": errors}


def _flag(kind: str, employer: str, message: str, sources: list[str], explanations: list[str], next_step: str) -> dict:
    return {"kind": kind, "employer": employer, "message": message, "sources": sources, "innocent_explanations": explanations, "next_step": next_step,
            "caution": "This shows a timing or count pattern in the records you entered. It does not show who was chosen or why."}


def analyze(data: dict) -> list[dict]:
    flags = []
    events = sorted(data["events"], key=lambda e: e["date"])
    for e in events:
        if e.get("notice_date"):
            lead = (date.fromisoformat(e["date"]) - date.fromisoformat(e["notice_date"])).days
            if lead < WARN_NOTICE_DAYS and (e["count"] >= AGGREGATION_THRESHOLD or e.get("kind") == "closure"):
                flags.append(_flag("short-notice", e["employer"], f"{e['employer']}: {e['count']} jobs cut on {e['date']}, notice dated {e['notice_date']} ({lead} days).",
                                   [e["source"]], ["The federal WARN Act covers only employers with 100+ workers and has exceptions (unforeseeable events, faltering company, pay in lieu).",
                                                   "The notice date entered may be a posting date, not the date employees were told."],
                                   "Check the employer's size and the state or federal notice itself for the date and stated basis."))
    by_employer: dict[str, list[dict]] = {}
    for e in events:
        by_employer.setdefault(e["employer"].strip().lower(), []).append(e)
    for group in by_employer.values():
        for i, first in enumerate(group):
            window = [x for x in group[i:] if (date.fromisoformat(x["date"]) - date.fromisoformat(first["date"])).days <= AGGREGATION_DAYS]
            total = sum(x["count"] for x in window)
            if len(window) > 1 and total >= AGGREGATION_THRESHOLD and all(x["count"] < AGGREGATION_THRESHOLD for x in window):
                flags.append(_flag("repeated-small-cuts", first["employer"], f"{first['employer']}: {len(window)} separate reductions within {AGGREGATION_DAYS} days totalling {total} jobs, each under {AGGREGATION_THRESHOLD}.",
                                   [x["source"] for x in window], ["Separate causes (lost contract, seasonal work, closures of different sites) are common.", "Whether the cuts count together under the law depends on facts not in these records."],
                                   "Ask the employer or the Arkansas Division of Workforce Services what notices were filed for each reduction."))
                break
    for e in events:
        titles = {t.strip().lower() for t in e.get("positions", "").split(";") if t.strip()}
        for post in data["postings"]:
            gap = (date.fromisoformat(post["date"]) - date.fromisoformat(e["date"])).days
            if post["employer"].strip().lower() == e["employer"].strip().lower() and post["title"].strip().lower() in titles and 0 <= gap <= REHIRE_DAYS:
                flags.append(_flag("position-reposted", e["employer"], f"{e['employer']}: '{post['title']}' was cut on {e['date']} and advertised again on {post['date']} ({gap} days).",
                                   [e["source"], post["source"]], ["The role may have been restructured, moved, or filled by transfer.", "Titles can be reused for different duties."],
                                   "Compare the job descriptions and ask what changed."))
    heads: dict[str, list[dict]] = {}
    for h in data["headcounts"]:
        heads.setdefault(h["employer"].strip().lower(), []).append(h)
    for name, series in heads.items():
        series.sort(key=lambda h: h["period_end"])
        for a, b in zip(series, series[1:]):
            drop = a["headcount"] - b["headcount"]
            stated = sum(e["count"] for e in by_employer.get(name, []) if a["period_end"] < e["date"] <= b["period_end"])
            if drop > 0 and abs(drop - stated) > HEADCOUNT_TOLERANCE * max(drop, stated, 1):
                flags.append(_flag("headcount-mismatch", a["employer"], f"{a['employer']}: headcount fell {drop} ({a['period_end']} to {b['period_end']}) but logged layoffs in that period total {stated}.",
                                   [a["source"], b["source"]], ["Attrition, retirements and transfers reduce headcount without layoffs.", "Headcounts may be counted differently (full-time vs. all staff)."],
                                   "Request the position control or payroll roster for both dates."))
    return flags


def report(path: Path | str) -> dict:
    data = load(path)
    return {"data": data, "flags": analyze(data)}
