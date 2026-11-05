import json
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

import historical_archives
import autopopulate


def test_search_preserves_loc_ocr_and_indexes_it(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    calls = []

    def fake_get_json(url):
        calls.append(url)
        if urlparse(url).path == "/collections/chronicling-america/":
            query = parse_qs(urlparse(url).query)
            assert query["q"] == ["Paragould contract"]
            assert query["dates"][0].startswith("1900-")
            return {
                "pagination": {"total": 1},
                "results": [{
                    "id": "/resource/sn123/1920-01-02/ed-1/?sp=3&q=contract",
                    "title": "The Paragould Soliphone",
                    "date": "1920-01-02",
                }],
            }, b'{"results":[]}'
        assert url == "https://www.loc.gov/resource/sn123/1920-01-02/ed-1/?sp=3&fo=json"
        return {
            "full_text": "The Paragould contract was approved for $12,000 on January 2, 1920."
        }, b'{"full_text":"OCR text"}'

    monkeypatch.setattr(historical_archives, "_get_json", fake_get_json)
    result = historical_archives.search_chronicling_america(
        "Paragould contract", evidence, start_date="1900-01-01", max_results=10, delay=0
    )

    assert result["pages_preserved"] == 1
    assert result["catalog_only"] == 0
    assert result["matches"][0]["url"] == "https://www.loc.gov/resource/sn123/1920-01-02/ed-1/?sp=3"
    assert len(calls) == 2
    manifest = [json.loads(line) for line in (evidence / "historical-archive-manifest.jsonl").read_text().splitlines()]
    assert len(manifest) == 2
    assert all(row["legal_basis"] and row["sha256"] for row in manifest)
    assert manifest[1]["content_type"] == "text/plain"
    assert manifest[1]["method"] == "archive-ocr"
    assert "(OCR text)" in manifest[1]["label"]

    summary = autopopulate.ingest(evidence)
    assert summary["indexed"] == 2
    connection = sqlite3.connect(evidence / "search.sqlite")
    try:
        rows = connection.execute("SELECT title, content FROM documents WHERE content MATCH 'contract'").fetchall()
    finally:
        connection.close()
    assert any("Paragould contract" in content for _title, content in rows)


def test_archive_query_validates_dates_and_result_limit(tmp_path, monkeypatch):
    def unexpected_request(_url):
        raise AssertionError("Invalid input must not contact the archive.")

    monkeypatch.setattr(historical_archives, "_get_json", unexpected_request)
    with pytest.raises(ValueError, match="Start date must not be after end date"):
        historical_archives.search_chronicling_america(
            "Paragould", tmp_path, start_date="2020-01-01", end_date="1900-01-01"
        )
    with pytest.raises(ValueError, match="Maximum results"):
        historical_archives.search_chronicling_america("Paragould", tmp_path, max_results=101)


def test_searches_all_arkansas_digital_archive_collections(tmp_path, monkeypatch):
    calls = []

    def fake_get_json(url, host, source):
        calls.append((url, host, source))
        if "/search/" in url:
            return {
                "totalResults": 1,
                "items": [{"collectionAlias": "manuscripts", "itemId": "1296"}],
            }, b'{"totalResults":1}'
        return {
            "metadataFields": [
                {"key": "title", "value": "Paragould Incorporation"},
                {"key": "date", "value": "1883-03-03"},
                {"key": "rights", "value": "Public catalog record"},
            ],
            "text": "Paragould incorporated on March 3, 1883.",
        }, b'{"text":"Paragould incorporated on March 3, 1883."}'

    monkeypatch.setattr(historical_archives, "_get_json", fake_get_json)
    result = historical_archives.search_arkansas_digital_archives(
        "Paragould", tmp_path / "evidence", start_date="1880-01-01", end_date="1890-01-01", delay=0
    )

    assert result["pages_preserved"] == 1
    assert result["matches"][0]["archive"] == "Arkansas State Archives Digital Archives"
    assert result["matches"][0]["url"].endswith("/singleitem/collection/manuscripts/id/1296")
    assert all(host == historical_archives.DIGITAL_ARCHIVE_HOST for _url, host, _source in calls)
    manifest = [json.loads(line) for line in (tmp_path / "evidence" / "historical-archive-manifest.jsonl").read_text().splitlines()]
    assert manifest[1]["source_family"] == "arkansas-digital-archives"
    assert manifest[1]["rights"] == "Public catalog record"
    assert manifest[1]["method"] == "archive-text"
    assert "(archive text)" in manifest[1]["label"]


def test_search_archives_reports_both_catalogs(tmp_path, monkeypatch):
    results = []
    for archive_name, method in (
        ("Arkansas State Archives Digital Archives", "search_arkansas_digital_archives"),
        ("Library of Congress, Chronicling America", "search_chronicling_america"),
    ):
        monkeypatch.setattr(historical_archives, method, lambda *_args, _name=archive_name, **_kwargs: {
            "archive": _name,
            "pages_searched": 1,
            "pages_preserved": 1,
            "catalog_only": 0,
            "has_more": False,
            "matches": [{"archive": _name}],
            "errors": [],
        })

    result = historical_archives.search_archives("Paragould", tmp_path / "evidence")

    assert [archive["archive"] for archive in result["archives"]] == [
        "Arkansas State Archives Digital Archives",
        "Library of Congress, Chronicling America",
    ]
    assert result["pages_preserved"] == 2
    assert len(result["matches"]) == 2


def test_archive_item_links_cannot_escape_loc():
    assert historical_archives._archive_url({"id": "https://example.com/record"}) == ""
    assert historical_archives._archive_url({"id": "/resource/sn123/?sp=4"}) == "https://www.loc.gov/resource/sn123/?sp=4"
