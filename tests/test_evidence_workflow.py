from evidence_workflow import (
    EvidenceRecord,
    EvidenceState,
    ProtectionLevel,
    ReviewDisposition,
    ReviewWorkflow,
)


def test_public_record_requires_review_for_support():
    workflow = ReviewWorkflow()
    record = EvidenceRecord(
        record_id="r1",
        text="A payment was routed to a shell entity",
        evidence_state=EvidenceState.INFERRED,
        protection=ProtectionLevel.PUBLIC,
    )
    workflow.add_record(record)
    workflow.add_review("r1", "analyst", ReviewDisposition.NEEDS_REVIEW, "Needs corroboration", "Request ledger")
    assert record.is_publicly_reportable() is False


def test_supported_review_allows_public_summary():
    workflow = ReviewWorkflow()
    record = EvidenceRecord(
        record_id="r2",
        text="A public payment record matches the contract amount",
        evidence_state=EvidenceState.FACT,
        protection=ProtectionLevel.PUBLIC,
    )
    workflow.add_record(record)
    workflow.add_review("r2", "reviewer", ReviewDisposition.SUPPORTED, "Matches a public filing", "Attach source packet")
    assert record.is_publicly_reportable() is True


def test_restricted_material_never_public():
    record = EvidenceRecord(
        record_id="r3",
        text="Protected health record and identifiers",
        evidence_state=EvidenceState.CORROBORATED,
        protection=ProtectionLevel.RESTRICTED,
    )
    assert record.is_publicly_reportable() is False


def test_redaction_keeps_fact_without_identifier():
    record = EvidenceRecord(
        record_id="r4",
        text="John Doe was present at the meeting",
        evidence_state=EvidenceState.FACT,
        redaction_needed=True,
    )
    redacted = record.redact_subject_details()
    assert "[REDACTED]" in redacted
    assert "meeting" in redacted


def test_narrative_status_tracks_hypothesis():
    workflow = ReviewWorkflow()
    record = EvidenceRecord(record_id="r5", text="Pattern suggests coordination", evidence_state=EvidenceState.INFERRED)
    workflow.add_record(record)
    assert workflow.narrative_status("r5") == "working hypothesis"
    workflow.add_review("r5", "reviewer", ReviewDisposition.SUPPORTED, "Corroborated by two sources", "Prepare an oversight packet")
    assert workflow.narrative_status("r5") == "supported narrative"
