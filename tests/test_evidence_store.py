from pathlib import Path

from evidence_store import load_evidence_records, save_evidence_record, save_uploaded_evidence


def test_store_round_trip(tmp_path: Path):
    path = tmp_path / "evidence.json"
    record = {
        "title": "Public grant notice",
        "url": "https://example.gov/grant-notice",
        "summary": "Award notice on a public portal",
        "kind": "primary-source",
        "protection": "public",
        "lane": "public-record",
    }

    saved = save_evidence_record(path, record)
    loaded = load_evidence_records(path)

    assert saved["id"]
    assert loaded[0]["title"] == "Public grant notice"
    assert loaded[0]["url"] == "https://example.gov/grant-notice"


def test_uploaded_file_is_preserved_with_hash_and_capture_time(tmp_path: Path):
    saved = save_uploaded_evidence(
        tmp_path / "records.json", tmp_path / "uploads", "council-minutes.pdf", b"source bytes",
        {"title": "Council minutes", "protection": "restricted"},
    )

    assert (tmp_path / "uploads" / f"{saved['id']}-council-minutes.pdf").read_bytes() == b"source bytes"
    assert saved["sha256"]
    assert saved["captured_at"]


def test_evidence_record_preserves_optional_exact_citation(tmp_path: Path):
    saved = save_evidence_record(tmp_path / "records.json", {"title": "Minutes", "citation_page": "4", "citation_section": "Agenda item 7", "citation_excerpt": "Vote was recorded."})

    assert saved["citation_page"] == "4"
    assert saved["citation_section"] == "Agenda item 7"


def test_geographic_citation_requires_valid_coordinate_pair(tmp_path: Path):
    saved = save_evidence_record(tmp_path / "records.json", {"title": "Map", "latitude": "36.05", "longitude": "-90.49", "location_label": "Public building"})
    assert saved["latitude"] == 36.05

    try:
        save_evidence_record(tmp_path / "records.json", {"title": "Incomplete map", "latitude": "36.05"})
    except ValueError as error:
        assert "both latitude and longitude" in str(error)
    else:
        raise AssertionError("Expected coordinate validation error")
