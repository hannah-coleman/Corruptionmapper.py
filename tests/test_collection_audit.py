from collection_audit import audit_manifest, compare_captures, detect_source_changes


def test_audit_reports_limits_and_duplicate_content_without_claiming_misconduct():
    report = audit_manifest([
        {"url": "https://example.gov/a", "host": "example.gov", "status": "collected", "content_type": "text/html", "sha256": "same"},
        {"url": "https://example.gov/b", "host": "example.gov", "status": "collected", "content_type": "text/html", "sha256": "same"},
        {"url": "https://example.gov/c", "host": "example.gov", "status": "not-collected", "reason": "robots.txt disallows access"},
    ])

    assert report["totals"] == {"unique_urls": 3, "collected": 2, "unavailable": 1, "unique_hosts": 1}
    assert len(report["duplicate_content"]) == 1
    assert "do not establish misconduct" in report["interpretation"]


def test_change_detection_reports_only_observable_capture_changes():
    changes = detect_source_changes([
        {"url": "https://example.gov/a", "captured_at": "2026-01-01T00:00:00Z", "status": "collected", "sha256": "one"},
        {"url": "https://example.gov/a", "captured_at": "2026-01-02T00:00:00Z", "status": "collected", "sha256": "two"},
        {"url": "https://example.gov/a", "captured_at": "2026-01-03T00:00:00Z", "status": "not-collected", "reason": "HTTP 404"},
        {"url": "https://example.gov/b", "captured_at": "2026-01-01T00:00:00Z", "status": "not-collected"},
        {"url": "https://example.gov/b", "captured_at": "2026-01-02T00:00:00Z", "status": "collected", "sha256": "three"},
        {"url": "https://example.gov/c", "captured_at": "2026-01-01T00:00:00Z", "status": "collected", "sha256": "four"},
        {"url": "https://example.gov/c", "captured_at": "2026-01-02T00:00:00Z", "status": "collected", "sha256": "four"},
    ])

    assert {change["change_type"] for change in changes} == {"content-changed", "became-unavailable", "became-available", "content-unchanged"}


def test_capture_comparison_returns_bounded_text_diff(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "old.html").write_text("<p>Prior notice</p>", encoding="utf-8")
    (raw / "new.html").write_text("<p>Updated notice</p>", encoding="utf-8")
    result = compare_captures([
        {"url": "https://example.gov/a", "captured_at": "2026-01-01", "status": "collected", "sha256": "old", "raw_file": str(raw / "old.html")},
        {"url": "https://example.gov/a", "captured_at": "2026-01-02", "status": "collected", "sha256": "new", "raw_file": str(raw / "new.html")},
    ], "https://example.gov/a", tmp_path)

    assert result["available"] is True
    assert any("-Prior notice" in line for line in result["lines"])
    assert any("+Updated notice" in line for line in result["lines"])