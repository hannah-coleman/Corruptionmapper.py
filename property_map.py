"""Local property / business / church map built from records the user supplies.

Every place must cite the saved record it came from. Links between places are drawn only from
shared filed identifiers (owner of record, registered agent, entity ID, mailing address). Nothing is
geocoded by an outside service: coordinates are entered or imported by the user.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from uuid import uuid4

KINDS = {"property", "business", "church", "government", "nonprofit", "other"}
LINK_FIELDS = {"owner": "same owner of record", "agent": "same registered agent", "entity_id": "same entity ID", "mailing_address": "same mailing address"}
MAX_ROWS = 5000


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(value).lower())).strip()


def _coord(value, low: float, high: float):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Latitude and longitude must be numbers.") from error
    if not low <= number <= high:
        raise ValueError("Latitude or longitude is out of range.")
    return number


def load_places(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _clean(row: dict) -> dict:
    name = str(row.get("name", "")).strip()
    source = str(row.get("source", "")).strip()
    kind = str(row.get("kind", "property")).strip().lower() or "property"
    if not name:
        raise ValueError("Every place needs a name or address.")
    if not source:
        raise ValueError("Every place must cite its source (a saved record URL, file or filing number).")
    if kind not in KINDS:
        raise ValueError(f"Kind must be one of: {', '.join(sorted(KINDS))}.")
    place = {key: str(row.get(key, "")).strip() for key in ("name", "address", "parcel_id", "owner", "agent", "entity_id", "mailing_address", "note", "source", "source_date")}
    place.update({"kind": kind, "lat": _coord(row.get("lat"), -90, 90), "lon": _coord(row.get("lon"), -180, 180)})
    if (place["lat"] is None) != (place["lon"] is None):
        raise ValueError("Enter both latitude and longitude, or neither.")
    return place


def add_place(path: Path | str, row: dict) -> dict:
    place = _clean(row)
    places = load_places(path)
    place["id"] = str(uuid4())
    places.append(place)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(places, indent=2), encoding="utf-8")
    return place


def import_csv(path: Path | str, text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Import at most {MAX_ROWS} rows at a time.")
    cleaned, errors = [], []
    for number, row in enumerate(rows, start=2):
        try:
            cleaned.append(_clean({(k or "").strip().lower(): v for k, v in row.items()}))
        except ValueError as error:
            errors.append(f"Row {number}: {error}")
    places = load_places(path)
    for place in cleaned:
        place["id"] = str(uuid4())
    places += cleaned
    if cleaned:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(places, indent=2), encoding="utf-8")
    return {"added": len(cleaned), "errors": errors}


def links(places: list[dict]) -> list[dict]:
    """Pairs of places that share a filed identifier, each with the records that show it."""
    found = []
    for field, label in LINK_FIELDS.items():
        groups: dict[str, list[dict]] = {}
        for place in places:
            key = _norm(place.get(field, ""))
            if key:
                groups.setdefault(key, []).append(place)
        for key, members in groups.items():
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    found.append({"a": a["id"], "b": b["id"], "relation": label, "value": a[field],
                                  "sources": [a["source"], b["source"]],
                                  "caution": "A shared value can be a common filing service, lender or family name. Confirm before drawing a conclusion."})
    return found


def build_map(path: Path | str) -> dict:
    places = load_places(path)
    return {"places": places, "links": links(places), "unplaced": [p["id"] for p in places if p.get("lat") is None]}
