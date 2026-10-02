"""Load the text of a preserved source for fact extraction, verifying integrity first."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from evidence_store import load_evidence_records
from index_evidence import extract_html_text, extract_pdf_pages

TEXT_SUFFIXES = {".txt", ".md", ".csv"}


def _inside(path: Path, root: Path) -> bool:
    resolved, base = path.resolve(), root.resolve()
    return base == resolved or base in resolved.parents


def pages_for_file(path: Path, content_type: str = "") -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        pages = extract_pdf_pages(path)
        if not any(pages):
            raise ValueError("No extractable text in this PDF. It may be a scanned image, which needs OCR.")
        return pages
    if suffix in {".html", ".htm"} or content_type == "text/html":
        return [extract_html_text(path)]
    if suffix in TEXT_SUFFIXES:
        return [" ".join(path.read_text(encoding="utf-8", errors="replace").split())]
    raise ValueError("Unsupported file type. Use PDF, HTML, or plain text.")


def _verified(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ValueError("The preserved file is missing.")
    if not expected_sha256 or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Integrity check failed: the file does not match its recorded SHA-256.")


def load_evidence_source(records_path: Path, uploads_dir: Path, evidence_id: str) -> tuple[list[str], dict, str]:
    record = next((item for item in load_evidence_records(records_path) if item.get("id") == evidence_id), None)
    if record is None:
        raise ValueError("Preserved evidence record not found.")
    stored = Path(str(record.get("stored_file", "")))
    if not record.get("stored_file") or not _inside(stored, uploads_dir):
        raise ValueError("This record has no preserved file to read.")
    _verified(stored, str(record.get("sha256", "")))
    source = {"type": "evidence", "ref": evidence_id, "sha256": record["sha256"], "title": record.get("title", "")}
    return pages_for_file(stored), source, str(record.get("protection") or "restricted")


def load_captured_source(search_database: Path, evidence_root: Path, url: str) -> tuple[list[str], dict, str]:
    if not search_database.exists():
        raise ValueError("No captured pages are indexed yet.")
    connection = sqlite3.connect(search_database)
    try:
        row = connection.execute("SELECT raw_file, sha256, content_type, title FROM documents WHERE url = ? LIMIT 1", (url,)).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError("That URL is not among the captured pages.")
    raw_file, sha256, content_type, title = row
    path = Path(raw_file)
    if not _inside(path, evidence_root):
        raise ValueError("Captured file is outside the evidence directory.")
    _verified(path, sha256)
    return pages_for_file(path, content_type), {"type": "capture", "ref": url, "sha256": sha256, "title": title}, "public"
