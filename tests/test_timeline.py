from timeline import build_timeline


def test_timeline_orders_dated_items_and_keeps_missing_dates_visible():
    events = build_timeline(
        [{"id": "e1", "title": "Evidence", "recorded_at": "2026-01-02T00:00:00+00:00"}],
        [{"statement": "Question", "status": "question"}],
        [{"url": "https://example.gov", "captured_at": "2026-01-03T00:00:00+00:00", "status": "collected", "bytes": 5, "sha256": "abc"}],
    )

    assert [event["type"] for event in events] == ["collection", "evidence", "claim"]
    assert events[-1]["timestamp"] is None