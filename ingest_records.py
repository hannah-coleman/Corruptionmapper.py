#!/usr/bin/env python3
"""Ingest reviewed, normalized records into a Signal Ledger SQLite casefile."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from casefile_db import SCHEMA


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def ingest(database: Path, case_id: str, records_path: Path) -> int:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("The input must be a JSON array.")
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    inserted = 0
    try:
        for record in records:
            required = {"id", "subject", "claim", "source_url"}
            missing = required - record.keys()
            if missing:
                raise ValueError(f"Record {record.get('id', '<unknown>')} missing: {', '.join(sorted(missing))}")
            source_id = stable_id("source", record["source_url"])
            entity_id = stable_id("entity", record["subject"].strip().lower())
            connection.execute("INSERT OR IGNORE INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                source_id, case_id, record.get("source_title", record["source_url"]), record.get("issuer_or_account"),
                record["source_url"], record.get("source_family", "government"), record.get("access_method", "official-public-page"),
                record.get("sensitivity", "public"), record.get("storage_zone", "public-graph"), record.get("published_at"),
                record.get("captured_at"), record.get("sha256"), record.get("source_type", "primary-public-record"),
                json.dumps(record.get("access_limitations", []), sort_keys=True)))
            connection.execute("INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                entity_id, case_id, record["subject"], record.get("entity_type", "Unknown"), record.get("sensitivity", "public"),
                record.get("storage_zone", "public-graph"), record.get("entity_status", "unreviewed"), record.get("subject_summary", ""),
                record.get("x", 80 + (inserted % 6) * 120), record.get("y", 90 + (inserted // 6) * 120)))
            observation_id = record["id"]
            connection.execute("INSERT OR REPLACE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                observation_id, case_id, record.get("category", "government"), record.get("sensitivity", "public"),
                record.get("storage_zone", "public-graph"), record.get("lane", "emerging-circumstance"), record["claim"],
                record.get("event_date"), record.get("location"), record.get("confidence", "unrated"), record.get("next_test", ""),
                json.dumps([entity_id]), json.dumps([source_id]), json.dumps(record.get("alternative_explanations", [])),
                json.dumps(record.get("review_notes", []))))
            for linked in record.get("linked_subjects", []):
                linked_id = stable_id("entity", linked.strip().lower())
                connection.execute("INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    linked_id, case_id, linked, "Unknown", "public", "public-graph", "unreviewed", "", None, None))
                relationship_id = stable_id("relationship", f"{entity_id}:{linked_id}:{record.get('relation', 'linked-by-record')}")
                connection.execute("INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?)", (
                    relationship_id, case_id, entity_id, linked_id, record.get("relation", "linked-by-record"),
                    record.get("relationship_status", "unresolved"), json.dumps([source_id])))
            inserted += 1
        connection.commit()
    finally:
        connection.close()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest reviewed normalized records into a casefile.")
    parser.add_argument("records", type=Path, help="Reviewed JSON array of normalized records")
    parser.add_argument("--case-id", default="case-example-001")
    parser.add_argument("--database", type=Path, default=Path("evidence/signal-ledger.sqlite"))
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    print(f"Ingested {ingest(args.database, args.case_id, args.records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
