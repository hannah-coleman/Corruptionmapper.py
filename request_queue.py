from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def list_requests(path: Path | str) -> list[dict]:
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
        items = data.get("requests", [])
        return items if isinstance(items, list) else []
    return []


def add_request(path: Path | str, request: dict) -> dict:
    agency = str(request.get("agency", "")).strip()
    description = str(request.get("description", "")).strip()
    if not agency or not description:
        raise ValueError("Agency and a neutral records description are required.")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = list_requests(target)
    payload = dict(request)
    payload.setdefault("id", str(uuid4()))
    payload.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("status", "draft")
    payload.setdefault("response_evidence_ids", [])
    existing.append(payload)
    target.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return payload


def deadline_status(requests: list[dict], today: str) -> list[dict]:
    current_day = datetime.fromisoformat(today).date()
    risks = []
    for request in requests:
        if request.get("status") not in {"submitted", "pending"}:
            continue
        deadline = str(request.get("deadline", "")).strip()
        if not deadline:
            risks.append({"id": request.get("id"), "level": "missing-deadline", "message": "No response deadline recorded.", "agency": request.get("agency", "")})
            continue
        try:
            due_date = datetime.fromisoformat(deadline).date()
        except ValueError:
            risks.append({"id": request.get("id"), "level": "invalid-deadline", "message": "Recorded deadline is not a valid date.", "agency": request.get("agency", "")})
            continue
        days_remaining = (due_date - current_day).days
        level = "overdue" if days_remaining < 0 else "due-soon" if days_remaining <= 7 else "on-track"
        risks.append({"id": request.get("id"), "level": level, "days_remaining": days_remaining, "agency": request.get("agency", ""), "message": f"Response deadline is {due_date.isoformat()}."})
    return sorted(risks, key=lambda item: ({"overdue": 0, "due-soon": 1, "missing-deadline": 2, "invalid-deadline": 3, "on-track": 4}[item["level"]], item.get("days_remaining", 9999)))


def link_response_evidence(path: Path | str, request_id: str, evidence_id: str) -> dict:
    target = Path(path)
    requests = list_requests(target)
    for request in requests:
        if request.get("id") != request_id:
            continue
        evidence_ids = request.setdefault("response_evidence_ids", [])
        if evidence_id not in evidence_ids:
            evidence_ids.append(evidence_id)
        request["status"] = "response-received"
        request["response_recorded_at"] = datetime.now(timezone.utc).isoformat()
        target.write_text(json.dumps(requests, indent=2), encoding="utf-8")
        return request
    raise ValueError("Records request not found.")
