import json
import sqlite3
import sys
from pathlib import Path

import index_evidence
from index_evidence import extract_text


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref)
    return out


def test_pdf_text_is_extracted(tmp_path: Path):
    pdf = tmp_path / "minutes.pdf"
    pdf.write_bytes(make_pdf("Council approved the paving contract"))
    assert "paving contract" in extract_text(pdf, "application/pdf")


def test_corrupt_pdf_yields_empty_text_not_a_crash(tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    assert extract_text(bad, "application/pdf") == ""


def test_indexer_records_content_type_and_pdf_text(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(make_pdf("Budget amendment ordinance"))
    html = tmp_path / "a.html"
    html.write_text("<p>City agenda</p>", encoding="utf-8")
    manifest = tmp_path / "m.jsonl"
    items = [
        {"status": "collected", "url": "https://x.gov/a.pdf", "raw_file": str(pdf), "content_type": "application/pdf", "sha256": "1"},
        {"status": "collected", "url": "https://x.gov/a", "raw_file": str(html), "content_type": "text/html", "sha256": "2"},
    ]
    manifest.write_text("\n".join(json.dumps(item) for item in items), encoding="utf-8")
    database = tmp_path / "search.sqlite"
    monkeypatch.setattr(sys, "argv", ["index_evidence", str(manifest), "--database", str(database)])
    assert index_evidence.main() == 0
    rows = sqlite3.connect(database).execute("SELECT url, content_type FROM documents WHERE documents MATCH 'amendment'").fetchall()
    assert rows == [("https://x.gov/a.pdf", "application/pdf")]
