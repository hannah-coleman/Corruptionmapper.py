from __future__ import annotations

import json
import re
from difflib import unified_diff
from collections import Counter, defaultdict
from pathlib import Path


def load_manifest(path: Path | str) -> list[dict]:
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


def audit_manifest(entries: list[dict]) -> dict:
    latest_by_url = {}
    for entry in entries:
        if entry.get("url"):
            latest_by_url[entry["url"]] = entry
    latest = list(latest_by_url.values())
    collected = [entry for entry in latest if entry.get("status") == "collected"]
    unavailable = [entry for entry in latest if entry.get("status") != "collected"]
    by_hash = defaultdict(list)
    for entry in collected:
        if entry.get("sha256"):
            by_hash[entry["sha256"]].append(entry["url"])
    duplicate_content = [
        {"sha256": digest, "urls": sorted(urls), "message": "Multiple URLs returned identical content; count them as one source until independently verified."}
        for digest, urls in by_hash.items() if len(urls) > 1
    ]
    failures = [
        {"url": entry["url"], "reason": entry.get("reason", "Not collected"), "next_action": "Use the listed records custodian or official public-records process; do not bypass access controls."}
        for entry in unavailable
    ]
    return {
        "scope": "Approved public URLs only; no authentication, circumvention, or private-data collection.",
        "totals": {"unique_urls": len(latest), "collected": len(collected), "unavailable": len(unavailable), "unique_hosts": len({entry.get("host") for entry in latest if entry.get("host")})},
        "content_types": dict(Counter(entry.get("content_type", "unknown") for entry in collected)),
        "access_limitations": failures,
        "duplicate_content": duplicate_content,
        "interpretation": "Collection failures, duplicate pages, and blocked robots access identify coverage limits and records-request opportunities. They do not establish misconduct.",
    }


def detect_source_changes(entries: list[dict]) -> list[dict]:
    by_url = defaultdict(list)
    for entry in entries:
        if entry.get("url") and entry.get("captured_at"):
            by_url[entry["url"]].append(entry)

    changes = []
    for url, captures in by_url.items():
        ordered = sorted(captures, key=lambda entry: entry["captured_at"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_collected = previous.get("status") == "collected"
            current_collected = current.get("status") == "collected"
            if not previous_collected and current_collected:
                change_type = "became-available"
            elif previous_collected and not current_collected:
                change_type = "became-unavailable"
            elif previous_collected and current_collected and previous.get("sha256") != current.get("sha256"):
                change_type = "content-changed"
            elif previous_collected and current_collected:
                change_type = "content-unchanged"
            else:
                continue
            changes.append({
                "url": url,
                "change_type": change_type,
                "previous_captured_at": previous["captured_at"],
                "captured_at": current["captured_at"],
                "previous_sha256": previous.get("sha256", ""),
                "sha256": current.get("sha256", ""),
                "detail": current.get("reason", "") if change_type == "became-unavailable" else "Observable retrieval or content change; preserve both captures and verify the official record before interpreting it.",
            })
    return sorted(changes, key=lambda change: change["captured_at"], reverse=True)


def _source_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def compare_captures(entries: list[dict], url: str, evidence_root: Path | str, max_lines: int = 160) -> dict:
    captures = sorted([entry for entry in entries if entry.get("url") == url and entry.get("status") == "collected"], key=lambda entry: entry.get("captured_at", ""))
    if len(captures) < 2:
        return {"available": False, "message": "At least two successful captures are required for a text comparison."}
    previous, current = captures[-2:]
    root = Path(evidence_root).resolve()
    try:
        old_path = Path(previous["raw_file"]).resolve()
        new_path = Path(current["raw_file"]).resolve()
        if root not in old_path.parents or root not in new_path.parents:
            raise ValueError("Capture path is outside the evidence directory.")
        diff = list(unified_diff(_source_text(old_path), _source_text(new_path), fromfile="prior capture", tofile="latest capture", lineterm=""))
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        return {"available": False, "message": f"Text comparison unavailable: {error}"}
    return {
        "available": True,
        "url": url,
        "previous_captured_at": previous.get("captured_at"),
        "captured_at": current.get("captured_at"),
        "changed": previous.get("sha256") != current.get("sha256"),
        "lines": diff[:max_lines],
        "truncated": len(diff) > max_lines,
        "message": "Text-only comparison of preserved captures. Review the original files and official record before interpreting a change.",
    }