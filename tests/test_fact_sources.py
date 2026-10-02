import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from fact_sources import load_captured_source, load_evidence_source, pages_for_file
from tests.test_index_evidence import make_pdf


def record(tmp_path: Path, name: str, content: bytes, **extra):
    uploads = tmp_path / "uploads"
    uploads.mkdir(exist_ok=True)
    stored = uploads / name
    stored.write_bytes(content)
    rec = {"id": "r1", "title": name, "stored_file": str(stored), "sha256": hashlib.sha256(content).hexdigest(), **extra}
    (tmp_path / "records.json").write_text(json.dumps([rec]), encoding="utf-8")
    return rec


def test_evidence_source_loads_text_and_inherits_protection(tmp_path):
    record(tmp_path, "notes.txt", b"Warrant issued on March 3, 2026.", protection="counsel")
    pages, source, protection = load_evidence_source(tmp_path / "records.json", tmp_path / "uploads", "r1")
    assert pages == ["Warrant issued on March 3, 2026."]
    assert source["sha256"] and protection == "counsel"


def test_tampered_file_fails_integrity_check(tmp_path):
    rec = record(tmp_path, "notes.txt", b"original")
    Path(rec["stored_file"]).write_bytes(b"altered")
    with pytest.raises(ValueError, match="Integrity"):
        load_evidence_source(tmp_path / "records.json", tmp_path / "uploads", "r1")


def test_files_outside_uploads_are_refused(tmp_path):
    rec = record(tmp_path, "notes.txt", b"x")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"x")
    rec["stored_file"] = str(outside)
    (tmp_path / "records.json").write_text(json.dumps([rec]), encoding="utf-8")
    with pytest.raises(ValueError, match="no preserved file"):
        load_evidence_source(tmp_path / "records.json", tmp_path / "uploads", "r1")


def test_unsupported_and_scanned_files_give_clear_errors(tmp_path):
    image = tmp_path / "scan.png"
    image.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError, match="Unsupported"):
        pages_for_file(image)
    bad_pdf = tmp_path / "scan.pdf"
    bad_pdf.write_bytes(b"not text")
    with pytest.raises(ValueError, match="OCR"):
        pages_for_file(bad_pdf)


def test_pdf_pages_and_captured_source(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    pdf = evidence / "a.pdf"
    content = make_pdf("Approved March 3, 2026")
    pdf.write_bytes(content)
    database = tmp_path / "search.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE VIRTUAL TABLE documents USING fts5(url, title, content, source_family, captured_at, raw_file, sha256, content_type)")
    connection.execute("INSERT INTO documents VALUES ('https://x.gov/a.pdf', 'A', '', '', '', ?, ?, 'application/pdf')", (str(pdf), hashlib.sha256(content).hexdigest()))
    connection.commit()
    connection.close()
    pages, source, protection = load_captured_source(database, evidence, "https://x.gov/a.pdf")
    assert "March 3, 2026" in pages[0] and protection == "public" and source["type"] == "capture"
    with pytest.raises(ValueError, match="not among"):
        load_captured_source(database, evidence, "https://x.gov/other")
