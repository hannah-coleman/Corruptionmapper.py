from __future__ import annotations


def build_timeline(evidence: list[dict], claims: list[dict], manifest: list[dict]) -> list[dict]:
    events = []
    for entry in manifest:
        events.append({
            "timestamp": entry.get("captured_at"),
            "type": "collection",
            "status": entry.get("status", "unknown"),
            "title": entry.get("url", "Untitled URL"),
            "detail": entry.get("reason") or f"Preserved {entry.get('bytes', 0)} bytes with SHA-256 {entry.get('sha256', 'not recorded')}.",
        })
    for record in evidence:
        events.append({
            "timestamp": record.get("captured_at") or record.get("recorded_at"),
            "type": "evidence",
            "status": record.get("protection", "unclassified"),
            "title": record.get("title", "Untitled evidence"),
            "detail": f"Evidence ID: {record.get('id', 'not recorded')}",
        })
    for claim in claims:
        events.append({
            "timestamp": claim.get("recorded_at"),
            "type": "claim",
            "status": claim.get("status", "question"),
            "title": claim.get("statement", "Untitled claim"),
            "detail": claim.get("next_test") or "No next test recorded.",
        })
    return sorted(events, key=lambda event: (event["timestamp"] is not None, event["timestamp"] or ""), reverse=True)