from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from evidence_workflow import EvidenceState, ReviewDisposition, ProtectionLevel, ReviewNote
from claim_store import load_claims, save_claim

class ReviewEngine:
    """
    Central engine to manage the transition of claims and evidence 
    through the Evidence Ladder.
    """
    def __init__(self, claims_path: Path, evidence_path: Path, audit_path: Path):
        self.claims_path = claims_path
        self.evidence_path = evidence_path
        self.audit_path = audit_path

    def _get_evidence_record(self, record_id: str) -> dict:
        records = []
        if self.evidence_path.exists():
            records = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        for r in records:
            if r.get("id") == record_id:
                return r
        raise ValueError(f"Evidence record {record_id} not found.")

    def _save_evidence_records(self, records: List[dict]):
        self.evidence_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def review_claim(self, claim_id: str, reviewer: str, disposition: ReviewDisposition, rationale: str, next_action: str) -> dict:
        """
        Processes a human review of a claim and updates its status 
        based on the Evidence Ladder rules.
        """
        claims = load_claims(self.claims_path)
        claim = next((c for c in claims if c["id"] == claim_id), None)
        if not claim:
            raise ValueError("Claim not found.")

        # 1. Record the review
        review_entry = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": reviewer,
            "disposition": disposition,
            "rationale": rationale,
            "next_action": next_action,
        }
        claim.setdefault("reviews", []).append(review_entry)
        claim["review_status"] = disposition

        # 2. Evidence Ladder Logic
        # A claim becomes a 'finding' only if it is SUPPORTED and has >= 2 sources.
        source_ids = claim.get("source_ids", [])
        if disposition == ReviewDisposition.SUPPORTED and len(source_ids) >= 2:
            claim["status"] = "finding"
        elif disposition == ReviewDisposition.CONTRADICTED:
            claim["status"] = "contradicted"
        elif disposition == ReviewDisposition.INSUFFICIENT_EVIDENCE:
            claim["status"] = "question"
        else:
            claim["status"] = "working-hypothesis"

        # 3. Save and Audit
        from audit_log import append_entry
        append_entry(self.audit_path, "claim-reviewed", claim_id, {
            "reviewer": reviewer,
            "disposition": disposition,
            "new_status": claim["status"]
        })

        # Save back to disk
        self._save_claims(claims)
        return claim

    def _save_claims(self, claims: List[dict]):
        self.claims_path.write_text(json.dumps(claims, indent=2), encoding="utf-8")

    def review_fact(self, fact_id: str, reviewer: str, disposition: ReviewDisposition, rationale: str, next_action: str) -> dict:
        """
        Reviews a specific fact extracted from a document.
        """
        # Facts are typically stored in facts.json
        facts_path = self.evidence_path.parent / "facts.json"
        facts = []
        if facts_path.exists():
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
        
        fact = next((f for f in facts if f["id"] == fact_id), None)
        if not fact:
            raise ValueError("Fact not found.")

        review_entry = {
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": reviewer,
            "disposition": disposition,
            "rationale": rationale,
            "next_action": next_action,
        }
        fact.setdefault("reviews", []).append(review_entry)
        fact["status"] = disposition # Maps directly to ReviewDisposition for simplicity

        from audit_log import append_entry
        append_entry(self.audit_path, "fact-reviewed", fact_id, {
            "reviewer": reviewer,
            "disposition": disposition
        })

        facts_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")
        return fact
