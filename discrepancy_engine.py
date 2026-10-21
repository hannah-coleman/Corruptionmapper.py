"""Find places where two sourced facts give different values for what may be the same item.

This engine reports differences, never conclusions. Each flag records how the two facts were
linked, how far each fact has been reviewed, whether the sources are independent, and the
innocent explanations to rule out. Flags are closed only by a named human with a written note.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

DISPOSITIONS = {
    "explained": "Difference has an innocent or documented explanation",
    "confirmed-discrepancy": "Difference is real and unexplained; needs the controlling record",
    "false-positive": "The two facts do not describe the same item",
    "needs-records": "Cannot decide without a records request",
}
PROTECTION_RANK = {"public": 0, "public-graph": 0, "restricted": 1, "counsel": 2}
CONTEXT_OVERLAP_MIN = 0.2
CONTEXT_WINDOW = 70

_ANCHOR = re.compile(
    r"\b(Ordinance|Resolution|Contract|Bid|Proposal|RFP|RFQ|Invoice|Purchase\s+Order|PO|Case|Docket|Agenda\s+Item|Permit|Grant|Act|Bill)\s*(?:No\.?|Number|#)?\s*([A-Z]{0,4}-?\d[\w\-./]*)",
    re.IGNORECASE)
_CASE_NUMBER = re.compile(r"\b(\d{2}[A-Z]{2,3}-\d{2}-\d{1,6})\b")
_STOP = frozenset("""the and for that with this from was were are has have had not but will shall may would could their there which when
    where what who whom into onto over under between about after before during per its his her they them our your you any all each such than then
    also been being more most other some only just upon within without while these those said same""".split())
_NOISE = frozenset("jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june july august september october november december".split())

EXPLANATIONS = {
    "date": [
        "One date may be the scheduled date and the other the actual, filing, or effective date.",
        "One document may have been amended or superseded.",
        "One may be a typographical error in a draft or summary.",
    ],
    "amount": [
        "One may be the budgeted or authorized amount and the other the amount paid.",
        "One may be the original amount and the other an amended amount or change order.",
        "The figures may cover different periods, line items, or include and exclude fees or tax.",
    ],
    "vote": [
        "The tallies may belong to different motions, readings, or amendments of the same item.",
        "One may count abstentions or absences differently.",
        "One may be a draft or unofficial record.",
    ],
    "statement": ["The statements may refer to different times, parties, or conditions."],
}


def _anchors(text: str) -> set[str]:
    found = set()
    for label, number in _ANCHOR.findall(text):
        label = re.sub(r"\s+", " ", label.lower())
        found.add(f"{'purchase order' if label == 'po' else label}:{number.lower().rstrip('.,;')}")
    found.update(f"case:{match.lower()}" for match in _CASE_NUMBER.findall(text))
    return found


def _context(fact: dict) -> set[str]:
    passage, matched = fact["passage"], fact.get("matched_text", "")
    at = passage.find(matched) if matched else -1
    window = passage[max(0, at - CONTEXT_WINDOW):at + len(matched) + CONTEXT_WINDOW] if at >= 0 else passage
    words = re.findall(r"[a-z][a-z'-]{2,}", window.lower())
    return {word for word in words if word not in _STOP and word not in _NOISE}


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _differs(a: dict, b: dict) -> dict | None:
    if a["value"] == b["value"]:
        return None
    kind = a["kind"]
    try:
        if kind == "amount":
            x, y = Decimal(a["value"]), Decimal(b["value"])
            return {"summary": f"Amounts differ by ${abs(x - y):,.2f} (${x:,.2f} vs ${y:,.2f}).", "delta": str(abs(x - y))}
        if kind == "date":
            x, y = date.fromisoformat(a["value"]), date.fromisoformat(b["value"])
            return {"summary": f"Dates differ by {abs((x - y).days)} day(s) ({x.isoformat()} vs {y.isoformat()}).", "delta": str(abs((x - y).days))}
    except (ValueError, ArithmeticError):
        pass
    return {"summary": f"Values differ ({a['value']} vs {b['value']}).", "delta": ""}


def _link(a: dict, b: dict) -> tuple[str, str] | None:
    if a["kind"] != b["kind"]:
        return None
    if a.get("subject") and b.get("subject") and a["subject"].casefold() == b["subject"].casefold() and a["attribute"].casefold() == b["attribute"].casefold():
        return "reviewer-linked", f"{a['subject']} | {a['attribute']}"
    shared = _anchors(a["passage"]) & _anchors(b["passage"])
    if shared and _overlap(_context(a), _context(b)) >= CONTEXT_OVERLAP_MIN:
        return "shared-identifier", sorted(shared)[0]
    return None


def _snapshot(fact: dict) -> dict:
    keys = ("id", "kind", "value", "unit", "passage", "matched_text", "page", "status", "source", "protection", "subject", "attribute")
    return {key: fact[key] for key in keys if key in fact}


def _tier(basis: str, reviewed: int) -> int:
    if basis == "reviewer-linked":
        return 1 if reviewed == 2 else 2
    return 2 if reviewed == 2 else 3


def build_flags(facts: list[dict]) -> list[dict]:
    live = [fact for fact in facts if fact.get("status") in {"proposed", "confirmed"}]
    buckets: dict[tuple, list[dict]] = {}
    for fact in live:
        if fact.get("subject"):
            buckets.setdefault(("subject", fact["kind"], fact["subject"].casefold(), fact["attribute"].casefold()), []).append(fact)
        for anchor in _anchors(fact["passage"]):
            buckets.setdefault(("anchor", fact["kind"], anchor), []).append(fact)
    flags: dict[str, dict] = {}
    for members in buckets.values():
        for index, a in enumerate(members):
            for b in members[index + 1:]:
                if a["id"] == b["id"]:
                    continue
                difference = _differs(a, b)
                link = _link(a, b) if difference else None
                if not link:
                    continue
                first, second = sorted((a, b), key=lambda fact: fact["id"])
                flag_id = hashlib.sha256(f"{first['id']}|{second['id']}".encode()).hexdigest()[:16]
                if flag_id in flags:
                    continue
                reviewed = sum(fact["status"] == "confirmed" for fact in (a, b))
                same_document = a["source"]["sha256"] == b["source"]["sha256"]
                protection = max((a.get("protection", "restricted"), b.get("protection", "restricted")), key=lambda p: PROTECTION_RANK.get(p, 1))
                flags[flag_id] = {
                    "id": flag_id, "type": "value-conflict", "kind": a["kind"],
                    "message": f"Two sources give different {a['kind']} values for what may be the same item. {difference['summary']}",
                    "link": {"basis": link[0], "detail": link[1]},
                    "vector": {
                        "link_strength": link[0],
                        "fact_review": {2: "both-confirmed", 1: "one-confirmed", 0: "unconfirmed"}[reviewed],
                        "source_independence": "same-document" if same_document else "independent-sources",
                    },
                    "tier": _tier(link[0], reviewed),
                    "difference": difference, "facts": [_snapshot(first), _snapshot(second)],
                    "innocent_explanations": EXPLANATIONS.get(a["kind"], EXPLANATIONS["statement"]),
                    "protection": protection, "status": "open",
                    "next_action": "Read both passages in context. If the difference is real, request the controlling record (adopted ordinance, executed contract, certified minutes) from its custodian.",
                }
    return sorted(flags.values(), key=lambda flag: (flag["tier"], flag["id"]))


def load_flags(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _write(path: Path | str, flags: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(flags, indent=2), encoding="utf-8")


def scan(path: Path | str, facts: list[dict]) -> dict:
    """Merge fresh findings into the stored flags, preserving every human review."""
    now = datetime.now(timezone.utc).isoformat()
    stored = {flag["id"]: flag for flag in load_flags(path)}
    fresh = {flag["id"]: flag for flag in build_flags(facts)}
    added = 0
    for flag_id, flag in fresh.items():
        if flag_id not in stored:
            flag["detected_at"] = now
            stored[flag_id] = flag
            added += 1
        elif stored[flag_id]["status"] in {"open", "stale"}:
            stored[flag_id].update({key: flag[key] for key in ("vector", "tier", "facts", "difference", "message")})
            stored[flag_id]["status"] = "open"
    stale = 0
    for flag_id, flag in stored.items():
        if flag_id not in fresh and flag["status"] == "open":
            flag["status"] = "stale"
            flag["stale_since"] = now
            stale += 1
    _write(path, list(stored.values()))
    return {"flags": len(stored), "added": added, "marked_stale": stale}


def review_flag(path: Path | str, flag_id: str, review: dict) -> dict:
    disposition = str(review.get("disposition", "")).strip()
    reviewer = str(review.get("reviewer", "")).strip()
    note = str(review.get("note", "")).strip()
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Disposition must be one of: {', '.join(DISPOSITIONS)}.")
    if not reviewer or not note:
        raise ValueError("A reviewer name and a written note are required to close a flag.")
    flags = load_flags(path)
    for flag in flags:
        if flag["id"] != flag_id:
            continue
        flag.setdefault("reviews", []).append({"disposition": disposition, "reviewer": reviewer, "note": note, "reviewed_at": datetime.now(timezone.utc).isoformat()})
        flag["status"] = disposition
        _write(path, flags)
        return flag
    raise ValueError("Discrepancy not found.")
