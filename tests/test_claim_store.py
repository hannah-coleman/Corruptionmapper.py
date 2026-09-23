from claim_store import research_queue, review_claim, save_claim


def test_finding_without_corroboration_is_stored_as_hypothesis(tmp_path):
    claim = save_claim(tmp_path / "claims.json", {
        "statement": "A reported tunnel connects two buildings.",
        "status": "finding",
        "source_ids": ["record-001"],
        "alternative_explanations": ["The reference may describe an old utility route."],
        "next_test": "Request historic utility and building-permit records.",
        "review_status": "unreviewed",
    })

    assert claim["status"] == "working-hypothesis"
    assert claim["requested_status"] == "finding"


def test_supported_claim_with_two_sources_can_be_a_finding(tmp_path):
    claim = save_claim(tmp_path / "claims.json", {
        "statement": "Two records describe the same documented connection.",
        "status": "finding",
        "source_ids": ["record-001", "record-002"],
        "alternative_explanations": ["The records may concern separate projects."],
        "next_test": "Compare the project identifiers and dates.",
        "review_status": "supported",
    })

    assert claim["status"] == "finding"


def test_research_queue_prioritizes_missing_test_then_missing_evidence():
    queue = research_queue([
        {"id": "with-test", "statement": "Documented question", "status": "question", "source_ids": [], "next_test": "Request the permit."},
        {"id": "no-test", "statement": "Unframed question", "status": "question", "source_ids": [], "next_test": ""},
        {"id": "finding", "statement": "Reviewed finding", "status": "finding", "source_ids": ["a", "b"], "next_test": ""},
    ])

    assert [item["claim_id"] for item in queue] == ["no-test", "with-test"]


def test_supported_review_with_two_sources_promotes_claim_to_finding(tmp_path):
    path = tmp_path / "claims.json"
    claim = save_claim(path, {"statement": "Two records match.", "status": "working-hypothesis", "source_ids": ["a", "b"]})
    reviewed = review_claim(path, claim["id"], {"reviewer": "Reviewer", "disposition": "supported", "rationale": "Records agree.", "counterevidence": "No conflicting record located.", "next_action": "Prepare for counsel review."})

    assert reviewed["status"] == "finding"
    assert reviewed["reviews"][0]["disposition"] == "supported"