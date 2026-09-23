from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from evidence_workflow import EvidenceRecord, EvidenceState, ProtectionLevel, ReviewDisposition
from legal_relevance import LegalRelevanceEngine
from records_gap_planner import GapPlanner
from safety_model import SafetyModel


@dataclass
class ReviewPacket:
    issue: str
    summary: str
    supported_facts: List[str]
    inferences: List[str]
    counterevidence: List[str]
    unanswered_questions: List[str]
    next_steps: List[str]
    legal_links: List[Dict[str, Any]]
    missing_records: List[Dict[str, Any]] = field(default_factory=list)
    foia_requests: List[Dict[str, Any]] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    publication_status: str = "restricted"


class PacketBuilder:
    """Generate a review-ready investigative packet from evidence, risk, and legal relevance."""

    def __init__(self):
        self.legal_engine = LegalRelevanceEngine()
        self.gap_planner = GapPlanner()
        self.safety = SafetyModel()

    def build_packet(
        self,
        issue: str,
        facts: List[str],
        inferences: List[str],
        counterevidence: List[str],
        unanswered_questions: Optional[List[str]] = None,
        evidence_records: Optional[List[EvidenceRecord]] = None,
        agency: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> ReviewPacket:
        summary = self.legal_engine.summarize_issue(issue, facts, inferences, counterevidence)
        missing = self.gap_planner.suggest_missing_records([
            {"text": item} for item in facts + inferences + counterevidence
        ], entity_name=issue)
        foia = []
        if agency and purpose:
            foia = [self.gap_planner.draft_foia_request(agency=agency, record_types=[item.document_type for item in missing], purpose=purpose)]

        risk_flags = []
        if evidence_records:
            for record in evidence_records:
                if record.protection in (ProtectionLevel.RESTRICTED, ProtectionLevel.COUNSEL):
                    risk_flags.append(f"Restricted record: {record.record_id}")
                if record.evidence_state in (EvidenceState.INFERRED, EvidenceState.ALLEGATION, EvidenceState.UNRESOLVED):
                    risk_flags.append(f"Needs review before support: {record.record_id}")

        publication_status = "restricted"
        if all(
            self.safety.can_publish(record.related_subjects[0] if record.related_subjects else None, record.evidence_state)
            for record in (evidence_records or [])
        ) and not missing:
            publication_status = "review-ready"

        return ReviewPacket(
            issue=issue,
            summary=summary["summary"],
            supported_facts=summary["supported_facts"],
            inferences=summary["inferences"],
            counterevidence=summary["counterevidence"],
            unanswered_questions=summary["questions"],
            next_steps=summary["next_steps"],
            legal_links=summary["linked_rules"],
            missing_records=[{
                "document_type": item.document_type,
                "rationale": item.rationale,
                "likely_sources": item.likely_sources,
                "suggested_questions": item.suggested_questions,
                "urgency": item.urgency,
            } for item in missing],
            foia_requests=[{
                "agency": item.agency,
                "record_types": item.record_types,
                "purpose": item.purpose,
                "request_text": item.request_text,
            } for item in foia],
            risk_flags=risk_flags,
            publication_status=publication_status,
        )
