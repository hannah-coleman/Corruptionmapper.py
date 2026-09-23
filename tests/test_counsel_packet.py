from counsel_packet import build_counsel_packet


def test_packet_separates_open_questions_and_includes_only_cited_sources():
    packet = build_counsel_packet(
        [{
            "id": "claim-1", "statement": "Is the route documented?", "status": "question",
            "source_ids": ["source-1"], "alternative_explanations": ["May be a utility route."],
            "next_test": "Request plans.", "review_status": "unreviewed",
        }],
        [{"id": "source-1", "title": "Permit record", "protection": "public"}, {"id": "source-2", "title": "Unrelated record"}],
    )

    assert packet["findings"] == []
    assert packet["open_questions"][0]["statement"] == "Is the route documented?"
    assert [source["id"] for source in packet["source_index"]] == ["source-1"]