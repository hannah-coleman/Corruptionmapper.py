from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceState(str, Enum):
    COLLECTED = "collected"
    NORMALIZED = "normalized"
    REVIEWED = "reviewed"
    FACT = "fact"
    CORROBORATED = "corroborated"
    INFERRED = "inferred"
    ALLEGATION = "allegation"
    CONTRADICTED = "contradicted"
    EXCULPATORY = "exculpatory"
    UNRESOLVED = "unresolved"
    RESTRICTED = "restricted"
    REDACTED = "redacted"


class ReviewDisposition(str, Enum):
    UNSUPPORTED = "unsupported"
    NEEDS_REVIEW = "needs-review"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    COUNSEL_REVIEW = "counsel-review"
    OUT_OF_SCOPE = "out-of-scope"


class ProtectionLevel(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    COUNSEL = "counsel"


@dataclass
class ReviewNote:
    reviewer: str
    disposition: ReviewDisposition
    rationale: str
    next_action: str
    reviewed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EvidenceRecord:
    record_id: str
    text: str
    evidence_state: EvidenceState = EvidenceState.COLLECTED
    protection: ProtectionLevel = ProtectionLevel.PUBLIC
    source_ids: List[str] = field(default_factory=list)
    redaction_needed: bool = False
    notes: List[ReviewNote] = field(default_factory=list)
    related_subjects: List[str] = field(default_factory=list)

    def is_publicly_reportable(self) -> bool:
        if self.protection in (ProtectionLevel.RESTRICTED, ProtectionLevel.COUNSEL):
            return False
        if self.redaction_needed:
            return False
        if self.evidence_state in (
            EvidenceState.COLLECTED,
            EvidenceState.NORMALIZED,
            EvidenceState.INFERRED,
            EvidenceState.ALLEGATION,
            EvidenceState.UNRESOLVED,
            EvidenceState.RESTRICTED,
        ):
            return False
        if self.notes:
            latest = self.notes[-1]
            if latest.disposition in (ReviewDisposition.NEEDS_REVIEW, ReviewDisposition.UNSUPPORTED):
                return False
        return True

    def latest_disposition(self) -> Optional[ReviewDisposition]:
        if not self.notes:
            return None
        return self.notes[-1].disposition

    def redact_subject_details(self) -> str:
        if not self.redaction_needed:
            return self.text
        redacted_tokens = []
        for token in self.text.split():
            if token[:1].isupper() and token[-1:] not in {".", ","}:
                redacted_tokens.append("[REDACTED]")
            else:
                redacted_tokens.append(token)
        return " ".join(redacted_tokens)


class ReviewWorkflow:
    def __init__(self):
        self.records: Dict[str, EvidenceRecord] = {}

    def add_record(self, record: EvidenceRecord) -> None:
        self.records[record.record_id] = record

    def add_review(self, record_id: str, reviewer: str, disposition: ReviewDisposition, rationale: str, next_action: str) -> ReviewNote:
        record = self.records[record_id]
        note = ReviewNote(reviewer=reviewer, disposition=disposition, rationale=rationale, next_action=next_action)
        record.notes.append(note)
        if disposition == ReviewDisposition.SUPPORTED:
            record.evidence_state = EvidenceState.CORROBORATED
        elif disposition == ReviewDisposition.CONTRADICTED:
            record.evidence_state = EvidenceState.CONTRADICTED
        elif disposition == ReviewDisposition.INSUFFICIENT_EVIDENCE:
            record.evidence_state = EvidenceState.UNRESOLVED
        elif disposition == ReviewDisposition.COUNSEL_REVIEW:
            record.protection = ProtectionLevel.COUNSEL
        return note

    def narrative_status(self, record_id: str) -> str:
        record = self.records[record_id]
        latest = record.latest_disposition()
        if latest == ReviewDisposition.SUPPORTED:
            return "supported narrative"
        if latest == ReviewDisposition.CONTRADICTED:
            return "contradicted narrative"
        if latest == ReviewDisposition.COUNSEL_REVIEW:
            return "counsel review pending"
        return "working hypothesis"

    def route_zone(self, protection: ProtectionLevel) -> str:
        if protection == ProtectionLevel.PUBLIC:
            return "public-graph"
        if protection == ProtectionLevel.RESTRICTED:
            return "restricted-vault"
        return "counsel-protected"
