import hashlib
import json

import autopopulate
import facts


def _capture(evidence, name, text, url):
    raw = evidence / "raw" / name
    raw.parent.mkdir(parents=True, exist_ok=True)
    data = f"<html><body>{text}</body></html>".encode()
    raw.write_bytes(data)
    return {"status": "collected", "url": url, "raw_file": str(raw), "content_type": "text/html",
            "sha256": hashlib.sha256(data).hexdigest(), "captured_at": "2026-01-01T00:00:00+00:00"}


def test_ingest_registers_indexes_extracts_and_is_idempotent(tmp_path):
    evidence = tmp_path / "evidence"
    items = [
        _capture(evidence, "a.bin", "The council approved the Main Street paving contract for $100,000 on March 3, 2025.", "https://example.gov/a"),
        _capture(evidence, "b.bin", "The council approved the Main Street paving contract for $250,000 on March 3, 2025.", "https://example.gov/b"),
    ]
    (evidence / "manifest.jsonl").write_text("\n".join(json.dumps(i) for i in items) + "\n", encoding="utf-8")

    first = autopopulate.ingest(evidence)
    assert first["captures"] == 2 and first["indexed"] == 2 and first["records_added"] == 2
    assert first["facts_proposed"] > 0
    records = json.loads((evidence / "records.json").read_text())
    assert all(r["protection"] == "public" for r in records)
    assert all(f["status"] == "proposed" for f in facts.load_facts(evidence / "facts.json"))

    second = autopopulate.ingest(evidence)
    assert second["records_added"] == 0 and second["facts_proposed"] == 0


def test_tampered_capture_is_rejected(tmp_path):
    evidence = tmp_path / "evidence"
    item = _capture(evidence, "a.bin", "Budget $5,000", "https://example.gov/a")
    (evidence / "manifest.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
    (evidence / "raw" / "a.bin").write_bytes(b"changed")
    summary = autopopulate.ingest(evidence)
    assert summary["captures"] == 0 and summary["rejected_failed_integrity"] == 1
