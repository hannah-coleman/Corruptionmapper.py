from safety_model import (
    EvidenceState,
    ProtectionLevel,
    ReviewDisposition,
    SafetyModel,
    VulnerableSubject,
)


def test_public_export_blocks_protected_material():
    report = SafetyModel()
    subject = VulnerableSubject("minor", "child")
    assert report.can_publish(subject, EvidenceState.CORROBORATED) is False


def test_unreviewed_material_is_not_public():
    report = SafetyModel()
    assert report.can_publish("public", EvidenceState.UNREVIEWED) is False


def test_redaction_keeps_facts_without_identifiers():
    report = SafetyModel()
    redacted = report.redact_subject_details("John Doe was present at the meeting", "minor")
    assert "John Doe" not in redacted
    assert "meeting" in redacted


def test_working_hypothesis_requires_review_before_support():
    report = SafetyModel()
    assert report.review_ready(EvidenceState.INFERRED, ReviewDisposition.UNRESOLVED) is False
    assert report.review_ready(EvidenceState.CORROBORATED, ReviewDisposition.SUPPORTED) is True


def test_sensitive_record_must_route_to_restricted_zone():
    report = SafetyModel()
    assert report.route_zone(ProtectionLevel.RESTRICTED) == "restricted-vault"
    assert report.route_zone(ProtectionLevel.PUBLIC) == "public-graph"
