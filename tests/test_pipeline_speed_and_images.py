import sys
from pathlib import Path

import pytest

import facts
import index_evidence as ie
import user_records as ur


def fact(i):
    return {"id": f"f{i}", "kind": "date", "value": "x"}


def test_save_proposed_dedupes_inside_one_batch_and_skips_rewrite_when_nothing_new(tmp_path):
    path = tmp_path / "facts.json"
    assert facts.save_proposed(path, [fact(1), fact(1), fact(2)])["added"] == 2
    before = path.stat().st_mtime_ns
    assert facts.save_proposed(path, [fact(1)])["added"] == 0
    assert path.stat().st_mtime_ns == before and len(facts.load_facts(path)) == 2


def test_pdf_pages_are_parsed_once_per_unchanged_file(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    calls = []
    monkeypatch.setattr(ie, "_extract_pdf_pages", lambda p: calls.append(p) or ["page one"])
    assert ie.extract_pdf_pages(pdf) == ["page one"] and ie.extract_pdf_pages(pdf) == ["page one"]
    assert len(calls) == 1
    pdf.write_bytes(b"%PDF-1.4 changed content")
    ie.extract_pdf_pages(pdf)
    assert len(calls) == 2


def test_cached_pages_cannot_be_mutated_by_callers(tmp_path, monkeypatch):
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    monkeypatch.setattr(ie, "_extract_pdf_pages", lambda p: ["a"])
    ie.extract_pdf_pages(pdf).append("junk")
    assert ie.extract_pdf_pages(pdf) == ["a"]


def test_images_are_accepted_for_indexing(tmp_path):
    stored = tmp_path / "evidence" / "uploads" / "scan.png"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"\x89PNG")
    record = {"id": "r9", "stored_file": str(stored), "original_filename": "scan.png", "title": "Scan", "protection": "public", "sha256": "ab", "size_bytes": 4}
    assert ur.register_for_indexing(tmp_path / "evidence", record)["indexed"]


@pytest.mark.skipif(sys.platform != "darwin", reason="image OCR uses macOS Vision")
def test_image_ocr_reads_text(tmp_path, monkeypatch):
    import ocr
    if ocr._binary() is None:
        pytest.skip("swiftc not available")
    import subprocess
    script = tmp_path / "mk.swift"
    out = tmp_path / "t.png"
    script.write_text('''import AppKit
let img = NSImage(size: NSSize(width: 900, height: 200))
img.lockFocus()
NSColor.white.setFill(); NSRect(x:0,y:0,width:900,height:200).fill()
"Resolution 12 approved".draw(at: NSPoint(x: 20, y: 80), withAttributes: [.font: NSFont.systemFont(ofSize: 44), .foregroundColor: NSColor.black])
img.unlockFocus()
try! NSBitmapImageRep(data: img.tiffRepresentation!)!.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "%s"))
''' % out)
    if subprocess.run(["swiftc", str(script), "-o", str(tmp_path / "mk")], capture_output=True).returncode != 0 or subprocess.run([str(tmp_path / "mk")]).returncode != 0:
        pytest.skip("could not build test image")
    monkeypatch.setattr(ocr, "CACHE", tmp_path / "ocrcache")
    assert "Resolution 12" in " ".join(ie.extract_image_pages(out))
