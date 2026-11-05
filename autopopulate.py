"""Turn already-collected public captures into searchable, comparable evidence.

Reads every collector/discovery manifest under the evidence directory, verifies each
capture against its recorded SHA-256, then (1) rebuilds the full-text index, (2) registers
each capture as a public evidence record, (3) extracts *proposed* facts and (4) scans them
for conflicting values. Nothing here fetches anything; collection stays in collector.py and
discover_public.py, which enforce robots.txt, rate limits and the approved-source scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import discrepancy_engine
import meeting_compare
import public_statements
import facts as facts_module
from evidence_store import load_evidence_records, save_evidence_record
from fact_sources import pages_for_file
from index_evidence import extract_text, title_for


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_captures(evidence_dir: Path) -> tuple[list[dict], int]:
    """Return unique, integrity-verified captures and a count of rejected entries."""
    captures: dict[str, dict] = {}
    rejected = 0
    root = evidence_dir.resolve()
    for manifest in sorted(evidence_dir.glob("*manifest*.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("status") != "collected" or not item.get("raw_file"):
                continue
            raw = Path(item["raw_file"])
            raw = raw if raw.is_absolute() else evidence_dir.parent / raw
            inside = root in raw.resolve().parents
            if not inside or not raw.is_file() or not item.get("sha256") or _sha256(raw) != item["sha256"]:
                rejected += 1
                continue
            captures.setdefault(item["sha256"], {**item, "path": raw})
    return list(captures.values()), rejected


def rebuild_index(captures: list[dict], database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TABLE IF EXISTS documents")
        connection.execute("CREATE VIRTUAL TABLE documents USING fts5(url, title, content, source_family, captured_at, raw_file, sha256, content_type)")
        for item in captures:
            try:
                content = extract_text(item["path"], item.get("content_type", ""))
            except Exception:
                content = ""
            connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                item.get("url", ""), title_for(item, item["path"]), content,
                item.get("source_family", "unclassified"), item.get("captured_at", ""),
                str(item["raw_file"]), item["sha256"], item.get("content_type", "")))
        connection.commit()
    finally:
        connection.close()
    return len(captures)


def register_records(captures: list[dict], records_path: Path) -> int:
    known = {record.get("id") for record in load_evidence_records(records_path)}
    added = 0
    for item in captures:
        record_id = f"capture-{item['sha256'][:16]}"
        if record_id in known:
            continue
        save_evidence_record(records_path, {
            "id": record_id, "title": title_for(item, item["path"]), "url": item.get("url", ""),
            "summary": "Automatically collected from an approved public source.",
            "kind": "captured-public-page", "protection": "public", "lane": "auto-collected",
            "stored_file": str(item["raw_file"]), "sha256": item["sha256"],
            "captured_at": item.get("captured_at", ""), "size_bytes": item.get("bytes", 0),
        })
        added += 1
    return added


def ingest(evidence_dir: Path | str = "evidence") -> dict:
    evidence_dir = Path(evidence_dir)
    captures, rejected = load_captures(evidence_dir)
    summary = {"captures": len(captures), "rejected_failed_integrity": rejected}
    summary["indexed"] = rebuild_index(captures, evidence_dir / "search.sqlite")
    summary["records_added"] = register_records(captures, evidence_dir / "records.json")

    facts_path = evidence_dir / "facts.json"
    batch, needs_ocr = [], []
    for item in captures:
        if item.get("content_type") == "application/json":
            continue  # preserved as evidence; its readable .txt rendering is what gets extracted
        source = {"type": "capture", "ref": item.get("url", ""), "sha256": item["sha256"], "title": title_for(item, item["path"])}
        try:
            pages = pages_for_file(item["path"], item.get("content_type", ""))
        except Exception:
            needs_ocr.append(item.get("url", ""))
            continue
        batch.extend(facts_module.extract_from_pages(pages, source, "public"))
    proposed = facts_module.save_proposed(facts_path, batch)["added"]  # one write for the whole run
    summary["facts_proposed"] = proposed
    summary["unreadable_or_scanned"] = needs_ocr
    summary["discrepancies"] = discrepancy_engine.scan(
        evidence_dir / "discrepancy-flags.json", facts_module.load_facts(facts_path),
        meeting_compare.meeting_flags(captures) + public_statements.compare(public_statements.load_statements(evidence_dir / "statements.json"), facts_module.load_facts(facts_path)))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Index, register, extract and compare collected public captures.")
    parser.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    args = parser.parse_args()
    print(json.dumps(ingest(args.evidence_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
