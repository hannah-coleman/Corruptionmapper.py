from __future__ import annotations

from datetime import datetime, timezone


def build_counsel_packet(claims: list[dict], evidence: list[dict]) -> dict:
    evidence_by_id = {record.get("id"): record for record in evidence if record.get("id")}
    citations = set()
    missing_citations = set()
    for claim in claims:
        for source_id in claim.get("source_ids", []):
            if source_id in evidence_by_id:
                citations.add(source_id)
            else:
                missing_citations.add(source_id)

    def claim_summary(status: str) -> list[dict]:
        return [
            {
                "id": claim.get("id"),
                "statement": claim.get("statement"),
                "source_ids": claim.get("source_ids", []),
                "alternative_explanations": claim.get("alternative_explanations", []),
                "next_test": claim.get("next_test", ""),
                "review_status": claim.get("review_status", "unreviewed"),
            }
            for claim in claims
            if claim.get("status") == status
        ]

    return {
        "packet_type": "counsel-review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "handling": "Internal research material. Claims are not allegations or findings unless labeled finding and independently reviewed.",
        "findings": claim_summary("finding"),
        "open_questions": claim_summary("question") + claim_summary("working-hypothesis"),
        "contradicted_claims": claim_summary("contradicted"),
        "source_index": [evidence_by_id[source_id] for source_id in sorted(citations)],
        "limitations": [
            "Open questions and working hypotheses require further verification.",
            "Alternative explanations must be evaluated alongside supporting evidence.",
            *([f"Claim references unavailable evidence record: {source_id}" for source_id in sorted(missing_citations)]),
        ],
    }