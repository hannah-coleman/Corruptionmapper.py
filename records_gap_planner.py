from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MissingRecord:
    document_type: str
    rationale: str
    likely_sources: List[str]
    supporting_evidence: List[str]
    suggested_questions: List[str]
    urgency: str = "medium"


@dataclass
class FOIADraft:
    agency: str
    record_types: List[str]
    purpose: str
    request_text: str
    notes: List[str] = field(default_factory=list)


class GapPlanner:
    """Suggest missing records and prepare lawful FOIA-style drafts."""

    KEYWORD_MAP = {
        "payment": {
            "document_type": "payment and procurement records",
            "likely_sources": ["city procurement office", "state accounting office", "vendor ledger", "contract file"],
            "questions": [
                "What payments were associated with this vendor or contract?",
                "What invoices, amendments, and approvals are on file?",
            ],
        },
        "contract": {
            "document_type": "contract and amendment files",
            "likely_sources": ["procurement office", "legal department", "vendor file", "agency contract archive"],
            "questions": [
                "What contract documents and amendments exist for this relationship?",
                "What approval chain is documented?",
            ],
        },
        "meeting": {
            "document_type": "meeting agendas, minutes, and attendance records",
            "likely_sources": ["city clerk", "board secretary", "agency records office", "meeting archive"],
            "questions": [
                "Who attended the relevant meeting?",
                "What agenda items and discussions are documented?",
            ],
        },
        "permit": {
            "document_type": "permit, inspection, and zoning files",
            "likely_sources": ["building department", "inspection office", "zoning office", "permit archive"],
            "questions": [
                "What applications or inspections are associated with the location or entity?",
                "Were any deviations or approvals documented?",
            ],
        },
        "fund": {
            "document_type": "fund transfer and grant records",
            "likely_sources": ["grant office", "budget office", "treasury", "oversight agency"],
            "questions": [
                "What transfers or grants are associated with this entity or program?",
                "What reporting and closeout records are on file?",
            ],
        },
        "court": {
            "document_type": "court docket and filings",
            "likely_sources": ["court clerk", "state judicial records system", "docket archive"],
            "questions": [
                "What docket entries and filing history exist for this matter?",
                "What orders, continuances, and judgments are on record?",
            ],
        },
    }

    def suggest_missing_records(self, evidence: List[Dict[str, Any]], entity_name: Optional[str] = None) -> List[MissingRecord]:
        missing: List[MissingRecord] = []
        seen: set[str] = set()

        for item in evidence:
            text = str(item.get("text", "")).lower()
            for keyword, config in self.KEYWORD_MAP.items():
                if keyword in text and config["document_type"] not in seen:
                    seen.add(config["document_type"])
                    missing.append(
                        MissingRecord(
                            document_type=config["document_type"],
                            rationale=f"Evidence describes a {keyword}-related event, but the corresponding official record set is not yet established.",
                            likely_sources=config["likely_sources"],
                            supporting_evidence=[str(item.get("text", ""))],
                            suggested_questions=config["questions"],
                            urgency="high" if keyword in {"payment", "court", "fund"} else "medium",
                        )
                    )

        if not missing and entity_name:
            missing.append(
                MissingRecord(
                    document_type="entity background and agency correspondence records",
                    rationale=f"An entity-specific pattern exists for {entity_name}, but direct records establishing the relationship are missing.",
                    likely_sources=["agency records office", "licensing office", "court clerk", "business registry"],
                    supporting_evidence=[f"Entity: {entity_name}"],
                    suggested_questions=[
                        "What agency records identify the entity and its authorized officials?",
                        "What correspondence, approvals, or filings exist for this relationship?",
                    ],
                    urgency="medium",
                )
            )

        return missing

    def draft_foia_request(self, agency: str, record_types: List[str], purpose: str, time_range: str = "relevant period") -> FOIADraft:
        types = ", ".join(record_types)
        text = (
            f"This request seeks {types} from {agency} for the period {time_range}. "
            f"The requested records are relevant to {purpose} and are needed to assess the completeness of the public record and identify any gaps in lawful oversight or disclosure. "
            "Please provide responsive records in the form in which they are kept, including metadata and indexes if available. "
            "If any portion is withheld, please identify the exemption and provide any segregable non-exempt material."
        )
        notes = [
            "Narrow the scope to the relevant period and entity or program.",
            "Preserve metadata, versions, and approval chains where available.",
            "The request should be specific, lawful, and limited to records relevant to the issue being assessed.",
        ]
        return FOIADraft(agency=agency, record_types=record_types, purpose=purpose, request_text=text, notes=notes)

    def build_case_gap_summary(self, evidence: List[Dict[str, Any]], agency: str, purpose: str, entity_name: Optional[str] = None) -> Dict[str, Any]:
        missing = self.suggest_missing_records(evidence, entity_name)
        drafts = [
            self.draft_foia_request(agency=agency, record_types=[item.document_type for item in missing], purpose=purpose)
        ] if missing else []
        return {
            "missing_records": [
                {
                    "document_type": item.document_type,
                    "rationale": item.rationale,
                    "likely_sources": item.likely_sources,
                    "supporting_evidence": item.supporting_evidence,
                    "suggested_questions": item.suggested_questions,
                    "urgency": item.urgency,
                }
                for item in missing
            ],
            "foia_requests": [
                {
                    "agency": item.agency,
                    "record_types": item.record_types,
                    "purpose": item.purpose,
                    "request_text": item.request_text,
                    "notes": item.notes,
                }
                for item in drafts
            ],
        }
