from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _digest(entry: dict) -> str:
    material = {key: value for key, value in entry.items() if key != "entry_hash"}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_entries(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    entries = []
    for line in target.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def append_entry(path: Path | str, action: str, object_id: str = "", details: dict | None = None) -> dict:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = read_entries(target)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "object_id": object_id,
        "details": details or {},
        "previous_hash": previous[-1].get("entry_hash", "") if previous else "",
    }
    entry["entry_hash"] = _digest(entry)
    with target.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def verify_log(path: Path | str) -> dict:
    entries = read_entries(path)
    previous_hash = ""
    issues = []
    for index, entry in enumerate(entries, start=1):
        if entry.get("previous_hash", "") != previous_hash:
            issues.append(f"Entry {index} has an unexpected previous hash.")
        if entry.get("entry_hash") != _digest(entry):
            issues.append(f"Entry {index} hash does not match its contents.")
        previous_hash = entry.get("entry_hash", "")
    return {"entries": len(entries), "valid": not issues, "issues": issues, "latest_hash": previous_hash}