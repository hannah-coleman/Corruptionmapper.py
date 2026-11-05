"""Citation-only register of known public controversies.

Stores a link, outlet, date and the researcher's own one-line summary. It never stores article text,
so nothing is copied; the point is to know what to check against the records.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4


def load_references(path: Path | str) -> list[dict]:
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_reference(path: Path | str, entry: dict) -> dict:
    url = str(entry.get("url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A reference needs a public http(s) link.")
    if parsed.netloc.lower().endswith(".onion"):
        raise ValueError("Onion addresses are not accepted; route anything of concern to the proper authorities instead.")
    summary = str(entry.get("summary", "")).strip()
    if not summary or len(summary) > 400:
        raise ValueError("Give a short summary in your own words (400 characters or fewer); article text is not stored.")
    record = {
        "id": str(uuid4()), "recorded_at": datetime.now(timezone.utc).isoformat(), "url": url,
        "outlet": str(entry.get("outlet", "")).strip(), "published": str(entry.get("published", "")).strip(),
        "topic": str(entry.get("topic", "")).strip(), "summary": summary,
        "records_to_check": [str(x).strip() for x in entry.get("records_to_check", []) if str(x).strip()],
        "status": "reported-not-verified",
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    items = load_references(target)
    items.append(record)
    target.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return record
