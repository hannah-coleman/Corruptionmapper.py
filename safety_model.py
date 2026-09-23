from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceState(str, Enum):
    UNREVIEWED = "unreviewed"
    INFERRED = "inferred"
    CORROBORATED = "corroborated"
    CONTRADICTED = "contradicted"
    EXCULPATORY = "exculpatory"


class ProtectionLevel(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    COUNSEL = "counsel"


class ReviewDisposition(str, Enum):
    UNRESOLVED = "unresolved"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NEEDS_REVIEW = "needs-review"


@dataclass(frozen=True)
class VulnerableSubject:
    subject_type: str
    identifier: str


class SafetyModel:
    def can_publish(self, subject: object, state: EvidenceState) -> bool:
        if subject is not None and isinstance(subject, VulnerableSubject):
            return False
        if state in (EvidenceState.UNREVIEWED, EvidenceState.INFERRED):
            return False
        return True

    def redact_subject_details(self, text: str, subject_type: str) -> str:
        if subject_type in {"minor", "child", "victim", "witness", "vulnerable"}:
            tokens = text.split()
            redacted = []
            for token in tokens:
                if token[:1].isupper() and token[-1:] not in {".", ","}:
                    redacted.append("[REDACTED]")
                else:
                    redacted.append(token)
            return " ".join(redacted)
        return text

    def review_ready(self, state: EvidenceState, disposition: ReviewDisposition) -> bool:
        if state == EvidenceState.CORROBORATED and disposition == ReviewDisposition.SUPPORTED:
            return True
        return False

    def route_zone(self, protection: ProtectionLevel) -> str:
        if protection == ProtectionLevel.PUBLIC:
            return "public-graph"
        if protection == ProtectionLevel.RESTRICTED:
            return "restricted-vault"
        return "counsel-protected"
