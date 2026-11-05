"""Register public statements (e.g. an official's public post) and test them against collected records.

Only content the author made public. Nothing is scraped from a platform; the researcher records the
link, date and a short quote. Each check is a lead: a figure or date in a statement that no collected
record contains may simply mean the record has not been collected yet.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

_AMOUNT = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion|k)?", re.IGNORECASE)
_SCALE = {"million": 1_000_000, "billion": 1_000_000_000, "k": 1_000}
_INSTRUMENT = re.compile(r"\b(?:resolution|ordinance)\s+(?:no\.?\s*)?(\d{4}-\d{1,3})", re.IGNORECASE)


def load_statements(path: Path | str) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_statement(path: Path | str, entry: dict) -> dict:
    url = str(entry.get("url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.netloc.lower().endswith(".onion"):
        raise ValueError("A statement needs a public http(s) link to the post or page.")
    quote = str(entry.get("quote", "")).strip()
    author = str(entry.get("author", "")).strip()
    if not quote or len(quote) > 600:
        raise ValueError("Quote the relevant words exactly (600 characters or fewer).")
    if not author:
        raise ValueError("Say who made the statement.")
    record = {
        "id": str(uuid4()), "recorded_at": datetime.now(timezone.utc).isoformat(), "url": url,
        "platform": str(entry.get("platform", "")).strip(), "author": author, "role": str(entry.get("role", "")).strip(),
        "posted": str(entry.get("posted", "")).strip(), "quote": quote, "visibility": "public",
    }
    items = load_statements(path)
    items.append(record)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(items, indent=2), encoding="utf-8")
    return record


def _amounts(text: str) -> list[float]:
    values = []
    for match in _AMOUNT.finditer(text):
        try:
            values.append(float(match.group(1).replace(",", "")) * _SCALE.get((match.group(2) or "").lower(), 1))
        except ValueError:
            continue
    return values


def compare(statements: list[dict], facts: list[dict]) -> list[dict]:
    known = {round(float(f["value"]), 2) for f in facts if f.get("kind") == "amount" and f.get("value")}
    flags = []
    for item in statements:
        quote = item["quote"]
        unsupported = [v for v in _amounts(quote) if round(v, 2) not in known]
        for value in unsupported:
            flags.append({
                "id": f"stmt-{item['id'][:8]}-{int(value)}", "type": "statement-vs-record", "kind": "statement-amount",
                "message": f"{item['author']} stated ${value:,.0f}, but no collected record contains that amount.",
                "tier": 3, "status": "open", "protection": "public",
                "facts": [{"id": item["id"], "kind": "statement", "value": "", "passage": quote, "source": {"type": "public-post", "ref": item["url"], "title": f"{item['author']} ({item['platform'] or 'public statement'}, {item['posted'] or 'undated'})"}}],
                "link": {"basis": "researcher-registered", "detail": item["posted"]}, "vector": {"text_method": "researcher-quote"},
                "innocent_explanations": ["The relevant record may not have been collected yet.", "The figure may be rounded, a total, or a different fiscal period than the records collected.", "The quote may have been transcribed imprecisely."],
                "next_action": "Find the budget, contract or minutes the figure should come from and add or request it; compare the two figures directly.",
            })
        for number in _INSTRUMENT.findall(quote):
            if not any(number in str(f.get("passage", "")) for f in facts):
                flags.append({
                    "id": f"stmt-{item['id'][:8]}-{number}", "type": "statement-vs-record", "kind": "statement-instrument",
                    "message": f"{item['author']} cited {number}, which does not appear in any collected record.",
                    "tier": 3, "status": "open", "protection": "public",
                    "facts": [{"id": item["id"], "kind": "statement", "value": "", "passage": quote, "source": {"type": "public-post", "ref": item["url"], "title": item["author"]}}],
                    "link": {"basis": "researcher-registered", "detail": item["posted"]}, "vector": {"text_method": "researcher-quote"},
                    "innocent_explanations": ["The measure may be in minutes or an agenda not yet collected.", "The number may have been mistyped in the post."],
                    "next_action": "Search the Agenda Center and ask the City Clerk for the instrument.",
                })
    return flags
