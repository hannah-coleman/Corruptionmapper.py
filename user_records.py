"""Let users add their own records so they are searched and cross-referenced with everything else.

Only files the user marks as a public record are indexed. Restricted or counsel-protected files are
preserved (hashed and dated) but never indexed, because the comparison engine treats indexed text as
public. Indexing writes an entry to a manifest, which is what the pipeline reads and re-verifies.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CONTENT_TYPES = {".pdf": "application/pdf", ".html": "text/html", ".htm": "text/html", ".txt": "text/plain", ".md": "text/plain", ".csv": "text/plain",
                 ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".tif": "image/tiff", ".tiff": "image/tiff",
                 ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MANIFEST = "user-records-manifest.jsonl"


def register_for_indexing(evidence_dir: Path | str, record: dict) -> dict:
    """Return {"indexed": bool, "reason": str}; appends a manifest entry only when the file may be indexed."""
    if str(record.get("protection", "")) != "public":
        return {"indexed": False, "reason": "Saved but not indexed: only files marked as public records are searched and compared. Protected files stay private."}
    stored = Path(str(record.get("stored_file", "")))
    content_type = CONTENT_TYPES.get(stored.suffix.lower())
    if content_type is None:
        return {"indexed": False, "reason": "Saved but not indexed: use PDF, an image (png, jpg, tiff), Word (.docx), Excel (.xlsx), HTML or plain text (txt, md, csv)."}
    evidence_dir = Path(evidence_dir)
    entry = {"status": "collected", "method": "user-upload", "source_family": "user-record", "content_type": content_type,
             "url": f"local-record://{record['id']}/{record.get('original_filename', stored.name)}", "title": record.get("title", stored.name),
             "raw_file": str(stored), "sha256": record["sha256"], "captured_at": record.get("captured_at") or datetime.now(timezone.utc).isoformat(),
             "bytes": record.get("size_bytes", 0), "host": "local-upload"}
    with (evidence_dir / MANIFEST).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return {"indexed": True, "reason": "Queued for indexing and comparison."}
