"""Structured facts extracted from documents, each pinned to its exact source passage.

Extraction is deterministic (pattern rules, no model guesses). Every extracted fact starts as
"proposed"; only a named human reviewer can confirm or reject it, and only confirmed facts
should feed comparison or hypothesis engines.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXTRACTOR = "rules-v1"
CONTEXT_CHARS = 140
MAX_FACTS_PER_DOCUMENT = 500
KINDS = {"date", "amount", "vote", "statement"}
DISPOSITIONS = {"confirmed", "rejected"}

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_DATE_TEXT = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE)
_DATE_US = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?(?:\s+(million|billion|thousand)\b|(?<=\d)([KMB])\b)?", re.IGNORECASE)
_SCALE = {"thousand": 1_000, "k": 1_000, "million": 1_000_000, "m": 1_000_000, "billion": 1_000_000_000, "b": 1_000_000_000}
_VOTE_KEYWORD = re.compile(r"\b(?:vote|voted|passed|approved|carried|adopted|failed|denied)\b[^.\d]{0,25}?(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\b", re.IGNORECASE)
_VOTE_SUFFIX = re.compile(r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s+vote\b", re.IGNORECASE)
_VOTE_AYES = re.compile(r"\bayes?\W{0,3}(\d{1,2})\W{1,12}(?:nays?|noes?)\W{0,3}(\d{1,2})\b", re.IGNORECASE)


def _valid_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _candidates(text: str) -> list[tuple[str, str, int, int, str]]:
    """Return (kind, value, start, end, unit) for every rule match, before dedupe."""
    found: list[tuple[str, str, int, int, str]] = []
    for match in _DATE_TEXT.finditer(text):
        iso = _valid_date(int(match.group(3)), _MONTHS[match.group(1)[:3].lower()], int(match.group(2)))
        if iso:
            found.append(("date", iso, match.start(), match.end(), ""))
    for match in _DATE_US.finditer(text):
        iso = _valid_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        if iso:
            found.append(("date", iso, match.start(), match.end(), ""))
    for match in _DATE_ISO.finditer(text):
        iso = _valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append(("date", iso, match.start(), match.end(), ""))
    for match in _AMOUNT.finditer(text):
        try:
            value = Decimal(match.group(1).replace(",", "") + (match.group(2) or ""))
        except InvalidOperation:
            continue
        suffix = (match.group(3) or match.group(4) or "").lower()
        if suffix:
            value *= _SCALE[suffix]
        found.append(("amount", f"{value:.2f}", match.start(), match.end(), "USD"))
    for pattern in (_VOTE_KEYWORD, _VOTE_SUFFIX, _VOTE_AYES):
        for match in pattern.finditer(text):
            found.append(("vote", f"{int(match.group(1))}-{int(match.group(2))}", match.start(), match.end(), "for-against"))
    return found


def _passage(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - CONTEXT_CHARS):end + CONTEXT_CHARS].split())


def fact_id(source_sha: str, page: int | None, kind: str, value: str, start: int) -> str:
    return hashlib.sha256(f"{source_sha}|{page}|{kind}|{value}|{start}".encode()).hexdigest()[:16]


def extract_from_pages(pages: list[str], source: dict, protection: str) -> list[dict]:
    """Extract proposed facts. `source` needs type, ref, sha256 and optional title; pages are 1-indexed."""
    now = datetime.now(timezone.utc).isoformat()
    facts: list[dict] = []
    seen: set[str] = set()
    for page_number, text in enumerate(pages, start=1):
        page = page_number if len(pages) > 1 else None
        kept_spans: list[tuple[str, str, int, int]] = []
        for kind, value, start, end, unit in sorted(_candidates(text), key=lambda item: item[2]):
            if any(k == kind and v == value and start < e and s < end for k, v, s, e in kept_spans):
                continue
            kept_spans.append((kind, value, start, end))
            identifier = fact_id(source["sha256"], page, kind, value, start)
            if identifier in seen:
                continue
            seen.add(identifier)
            facts.append({
                "id": identifier, "kind": kind, "value": value, "unit": unit,
                "matched_text": text[start:end], "passage": _passage(text, start, end),
                "page": page, "start": start, "end": end,
                "source": {key: source.get(key, "") for key in ("type", "ref", "sha256", "title")},
                "protection": protection, "status": "proposed",
                "extracted_by": EXTRACTOR, "extracted_at": now,
            })
            if len(facts) >= MAX_FACTS_PER_DOCUMENT:
                return facts
    return facts


def load_facts(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _write(path: Path | str, facts: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(facts, indent=2), encoding="utf-8")


def save_proposed(path: Path | str, new_facts: list[dict]) -> dict:
    existing = load_facts(path)
    known = {fact["id"] for fact in existing}
    added = [fact for fact in new_facts if fact["id"] not in known]
    _write(path, existing + added)
    return {"added": len(added), "already_present": len(new_facts) - len(added), "truncated": len(new_facts) >= MAX_FACTS_PER_DOCUMENT}


def review_fact(path: Path | str, fact_id_: str, review: dict) -> dict:
    disposition = str(review.get("disposition", "")).strip()
    reviewer = str(review.get("reviewer", "")).strip()
    note = str(review.get("note", "")).strip()
    corrected = str(review.get("corrected_value", "")).strip()
    if disposition not in DISPOSITIONS:
        raise ValueError("Disposition must be confirmed or rejected.")
    if not reviewer:
        raise ValueError("A reviewer name is required.")
    if disposition == "rejected" and not note:
        raise ValueError("A note explaining the rejection is required.")
    facts = load_facts(path)
    for fact in facts:
        if fact["id"] != fact_id_:
            continue
        if fact.get("status") != "proposed":
            raise ValueError("This fact has already been reviewed.")
        if corrected:
            if disposition == "rejected":
                raise ValueError("Only a confirmed fact can carry a corrected value.")
            fact["original_value"] = fact["value"]
            fact["value"] = corrected
        fact.update({"status": disposition, "reviewer": reviewer, "review_note": note, "reviewed_at": datetime.now(timezone.utc).isoformat()})
        _write(path, facts)
        return fact
    raise ValueError("Fact not found.")


def add_manual_fact(path: Path | str, entry: dict, source: dict, protection: str) -> dict:
    """A fact typed in by a person from a preserved source; the person is its reviewer."""
    kind = str(entry.get("kind", "")).strip()
    value = str(entry.get("value", "")).strip()
    passage = " ".join(str(entry.get("passage", "")).split())
    reviewer = str(entry.get("reviewer", "")).strip()
    if kind not in KINDS or not value or not passage or not reviewer:
        raise ValueError("Kind, value, the exact source passage, and your name are required.")
    if kind == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Dates must be YYYY-MM-DD.")
    if kind == "date" and _valid_date(*(int(part) for part in value.split("-"))) is None:
        raise ValueError("That is not a valid calendar date.")
    now = datetime.now(timezone.utc).isoformat()
    fact = {
        "id": fact_id(source["sha256"], None, kind, value, len(passage)), "kind": kind, "value": value,
        "unit": "USD" if kind == "amount" else "", "matched_text": value, "passage": passage,
        "page": entry.get("page") or None, "start": None, "end": None,
        "source": {key: source.get(key, "") for key in ("type", "ref", "sha256", "title")},
        "protection": protection, "status": "confirmed", "extracted_by": f"manual:{reviewer}", "extracted_at": now,
        "reviewer": reviewer, "review_note": "Entered manually from the preserved source.", "reviewed_at": now,
    }
    existing = load_facts(path)
    if any(item["id"] == fact["id"] for item in existing):
        raise ValueError("This fact is already recorded.")
    _write(path, existing + [fact])
    return fact
