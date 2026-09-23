from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def load_evidence_records(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        records = data.get("records", [])
        return records if isinstance(records, list) else []
    return []


def save_evidence_record(path: Path | str, record: dict) -> dict:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = load_evidence_records(target)
    payload = dict(record)
    payload.setdefault("id", str(uuid4()))
    payload.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    payload["citation_page"] = str(payload.get("citation_page", "")).strip()
    payload["citation_section"] = str(payload.get("citation_section", "")).strip()
    payload["citation_excerpt"] = str(payload.get("citation_excerpt", "")).strip()
    payload["location_label"] = str(payload.get("location_label", "")).strip()
    payload["geographic_source_url"] = str(payload.get("geographic_source_url", "")).strip()
    payload["imagery_captured_at"] = str(payload.get("imagery_captured_at", "")).strip()
    latitude = str(payload.get("latitude", "")).strip()
    longitude = str(payload.get("longitude", "")).strip()
    if bool(latitude) != bool(longitude):
        raise ValueError("Provide both latitude and longitude, or leave both blank.")
    if latitude:
        try:
            latitude_value, longitude_value = float(latitude), float(longitude)
        except ValueError as error:
            raise ValueError("Latitude and longitude must be valid numbers.") from error
        if not -90 <= latitude_value <= 90 or not -180 <= longitude_value <= 180:
            raise ValueError("Latitude or longitude is outside its valid range.")
        payload["latitude"] = latitude_value
        payload["longitude"] = longitude_value
    else:
        payload["latitude"] = ""
        payload["longitude"] = ""
    existing.append(payload)
    target.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return payload


def save_uploaded_evidence(records_path: Path | str, uploads_dir: Path | str, filename: str, content: bytes, metadata: dict) -> dict:
    safe_name = Path(filename).name
    if not safe_name:
        raise ValueError("A file name is required.")
    if not content:
        raise ValueError("The selected file is empty.")
    if len(content) > 25_000_000:
        raise ValueError("Files must be 25 MB or smaller.")

    record_id = str(uuid4())
    target_dir = Path(uploads_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_file = target_dir / f"{record_id}-{safe_name}"
    stored_file.write_bytes(content)
    record = {
        "id": record_id,
        "title": str(metadata.get("title") or safe_name),
        "url": "",
        "summary": str(metadata.get("summary") or "Local file preserved for review."),
        "kind": str(metadata.get("kind") or "primary-source"),
        "protection": str(metadata.get("protection") or "restricted"),
        "lane": str(metadata.get("lane") or "local-file"),
        "original_filename": safe_name,
        "stored_file": str(stored_file),
        "sha256": hashlib.sha256(content).hexdigest(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": len(content),
    }
    return save_evidence_record(records_path, record)
