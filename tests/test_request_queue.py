from request_queue import add_request, deadline_status, link_response_evidence, list_requests


def test_request_queue_round_trip(tmp_path):
    store = tmp_path / "requests.json"
    first = add_request(store, {
        "agency": "Paragould City Clerk",
        "record_type": "Contracts",
        "description": "Request bids and award files",
        "status": "draft",
    })
    second = add_request(store, {
        "agency": "Greene County Clerk",
        "record_type": "Minutes",
        "description": "Request meeting minutes and attendance",
        "status": "queued",
    })

    requests = list_requests(store)
    assert first["agency"] == "Paragould City Clerk"
    assert second["status"] == "queued"
    assert len(requests) == 2


def test_request_requires_agency_and_neutral_description(tmp_path):
    try:
        add_request(tmp_path / "requests.json", {"agency": "", "description": ""})
    except ValueError as error:
        assert "Agency" in str(error)
    else:
        raise AssertionError("Expected request validation error")


def test_deadline_status_only_assesses_submitted_requests_with_user_dates():
    risks = deadline_status([
        {"id": "late", "agency": "Clerk", "status": "submitted", "deadline": "2026-01-01"},
        {"id": "soon", "agency": "Treasurer", "status": "submitted", "deadline": "2026-01-08"},
        {"id": "draft", "agency": "Agency", "status": "draft", "deadline": "2025-01-01"},
        {"id": "none", "agency": "Office", "status": "pending", "deadline": ""},
    ], "2026-01-05")

    assert [risk["level"] for risk in risks] == ["overdue", "due-soon", "missing-deadline"]


def test_response_evidence_is_linked_once_and_updates_request_status(tmp_path):
    store = tmp_path / "requests.json"
    request = add_request(store, {"agency": "City Clerk", "description": "Meeting minutes"})
    linked = link_response_evidence(store, request["id"], "evidence-1")
    linked_again = link_response_evidence(store, request["id"], "evidence-1")

    assert linked["status"] == "response-received"
    assert linked_again["response_evidence_ids"] == ["evidence-1"]
