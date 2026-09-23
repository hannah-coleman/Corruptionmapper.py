from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


VALID_STATUSES = {"question", "working-hypothesis", "finding", "contradicted"}
VALID_DISPOSITIONS = {"supported", "contradicted", "insufficient-evidence", "needs-review", "counsel-review"}


def load_claims(path: Path | str) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def save_claim(path: Path | str, claim: dict) -> dict:
    statement = str(claim.get("statement", "")).strip()
    if not statement:
        raise ValueError("A claim needs a clear, testable statement.")

    source_ids = [str(item).strip() for item in claim.get("source_ids", []) if str(item).strip()]
    alternatives = [str(item).strip() for item in claim.get("alternative_explanations", []) if str(item).strip()]
    requested_status = str(claim.get("status", "question"))
    if requested_status not in VALID_STATUSES:
        raise ValueError("Unknown claim status.")

    review_status = str(claim.get("review_status", "unreviewed"))
    status = requested_status
    if requested_status == "finding" and (len(source_ids) < 2 or review_status != "supported"):
        status = "working-hypothesis"

    record = {
        "id": str(uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "statement": statement,
        "status": status,
        "requested_status": requested_status,
        "source_ids": source_ids,
        "alternative_explanations": alternatives,
        "next_test": str(claim.get("next_test", "")).strip(),
        "review_status": review_status,
        "reviews": [],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    claims = load_claims(target)
    claims.append(record)
    target.write_text(json.dumps(claims, indent=2), encoding="utf-8")
    return record


def review_claim(path: Path | str, claim_id: str, review: dict) -> dict:
    reviewer = str(review.get("reviewer", "")).strip()
    disposition = str(review.get("disposition", ""))
    rationale = str(review.get("rationale", "")).strip()
    counterevidence = str(review.get("counterevidence", "")).strip()
    next_action = str(review.get("next_action", "")).strip()
    if not reviewer or not rationale or not counterevidence or not next_action:
        raise ValueError("Reviewer, rationale, counterevidence, and next action are required.")
    if disposition not in VALID_DISPOSITIONS:
        raise ValueError("Unknown review disposition.")

    target = Path(path)
    claims = load_claims(target)
    for claim in claims:
        if claim.get("id") != claim_id:
            continue
        entry = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": reviewer,
            "disposition": disposition,
            "rationale": rationale,
            "counterevidence": counterevidence,
            "next_action": next_action,
        }
        claim.setdefault("reviews", []).append(entry)
        claim["review_status"] = disposition
        claim["next_test"] = next_action
        if disposition == "contradicted":
            claim["status"] = "contradicted"
        elif disposition == "supported" and len(claim.get("source_ids", [])) >= 2:
            claim["status"] = "finding"
        elif claim.get("status") != "question":
            claim["status"] = "working-hypothesis"
        target.write_text(json.dumps(claims, indent=2), encoding="utf-8")
        return claim
    raise ValueError("Claim not found.")


def research_queue(claims: list[dict]) -> list[dict]:
    queue = []
    for claim in claims:
        status = claim.get("status", "question")
        if status in {"finding", "contradicted"}:
            continue
        source_count = len(claim.get("source_ids", []))
        next_test = str(claim.get("next_test", "")).strip()
        if not next_test:
            priority, reason = 1, "Needs a specific next test before research begins."
        elif source_count == 0:
            priority, reason = 2, "No cited evidence yet; start with the named record or source."
        else:
            priority, reason = 3, "Has cited material; test it against an independent record."
        queue.append({
            "claim_id": claim.get("id"),
            "statement": claim.get("statement", ""),
            "status": status,
            "source_count": source_count,
            "next_test": next_test,
            "priority": priority,
            "reason": reason,
        })
    return sorted(queue, key=lambda item: (item["priority"], item["statement"].lower()))