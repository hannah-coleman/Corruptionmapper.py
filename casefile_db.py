#!/usr/bin/env python3
"""Initialize and import a local Signal Ledger casefile database."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, title TEXT NOT NULL,
    created_at TEXT, jurisdiction_json TEXT NOT NULL, scope_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), title TEXT NOT NULL,
    issuer_or_account TEXT, url TEXT, source_family TEXT, access_method TEXT,
    sensitivity TEXT NOT NULL, storage_zone TEXT NOT NULL, published_at TEXT,
    captured_at TEXT, sha256 TEXT, type TEXT, access_limitations_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), category TEXT NOT NULL,
    sensitivity TEXT NOT NULL, storage_zone TEXT NOT NULL, lane TEXT NOT NULL,
    text TEXT NOT NULL, event_date TEXT, location TEXT, confidence TEXT,
    next_test TEXT, actors_json TEXT NOT NULL, source_ids_json TEXT NOT NULL,
    alternative_explanations_json TEXT NOT NULL, review_notes_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), label TEXT NOT NULL,
    entity_type TEXT NOT NULL, sensitivity TEXT NOT NULL, storage_zone TEXT NOT NULL,
    status TEXT NOT NULL, summary TEXT, x REAL, y REAL
);
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), source_entity_id TEXT NOT NULL REFERENCES entities(id),
    target_entity_id TEXT NOT NULL REFERENCES entities(id), relation TEXT NOT NULL, evidence_status TEXT NOT NULL,
    source_ids_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logos_entries (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), observation_ids_json TEXT NOT NULL,
    rule_or_mechanism TEXT, inference TEXT, counterevidence_ids_json TEXT NOT NULL,
    status TEXT NOT NULL, reviewer TEXT, reviewed_at TEXT, next_action TEXT
);
CREATE TABLE IF NOT EXISTS discrepancies (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), kind TEXT NOT NULL,
    severity TEXT NOT NULL, message TEXT NOT NULL, disposition TEXT NOT NULL,
    recommended_desks_json TEXT NOT NULL, routing_rationale TEXT, next_action TEXT,
    record_ids_json TEXT NOT NULL, source_urls_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), action TEXT NOT NULL,
    actor TEXT, timestamp TEXT NOT NULL, object_id TEXT, reason TEXT, previous_version TEXT
);
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), jurisdiction TEXT,
    custodian TEXT, description TEXT NOT NULL, status TEXT NOT NULL, submitted_at TEXT,
    deadline TEXT, response_at TEXT, denial_reason TEXT, counsel_review TEXT
);
"""


def dump(value: object) -> str:
    return json.dumps(value if value is not None else [], sort_keys=True)


def import_case(database: Path, casefile_path: Path) -> None:
    casefile = json.loads(casefile_path.read_text(encoding="utf-8"))
    connection = sqlite3.connect(database)
    try:
        connection.executescript(SCHEMA)
        connection.execute("INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?, ?, ?)", (
            casefile["case_id"], casefile["schema_version"], casefile["title"],
            casefile.get("created_at"), dump(casefile["jurisdiction"]), dump(casefile["scope"])))
        for source in casefile.get("sources", []):
            connection.execute("INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                source["id"], casefile["case_id"], source["title"], source.get("issuer_or_account"),
                source.get("url"), source.get("source_family"), source.get("access_method"),
                source.get("sensitivity", "public"), source.get("storage_zone", "public-graph"),
                source.get("published_at"), source.get("captured_at"), source.get("sha256"),
                source.get("type"), dump(source.get("access_limitations"))))
        for observation in casefile.get("observations", []):
            connection.execute("INSERT OR REPLACE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                observation["id"], casefile["case_id"], observation["category"], observation["sensitivity"],
                observation["storage_zone"], observation["lane"], observation["text"], observation.get("event_date"),
                observation.get("location"), observation.get("confidence"), observation.get("next_test"),
                dump(observation.get("actors")), dump(observation.get("source_ids")),
                dump(observation.get("alternative_explanations")), dump(observation.get("review_notes"))))
        for entity in casefile.get("entities", []):
            connection.execute("INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                entity["id"], casefile["case_id"], entity["label"], entity["entity_type"],
                entity.get("sensitivity", "public"), entity.get("storage_zone", "public-graph"),
                entity.get("status", "unreviewed"), entity.get("summary"), entity.get("x"), entity.get("y")))
        for relationship in casefile.get("relationships", []):
            connection.execute("INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?)", (
                relationship["id"], casefile["case_id"], relationship["source_entity_id"],
                relationship["target_entity_id"], relationship["relation"], relationship.get("evidence_status", "unresolved"),
                dump(relationship.get("source_ids"))))
        for entry in casefile.get("logos", []):
            connection.execute("INSERT OR REPLACE INTO logos_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                entry["id"], casefile["case_id"], dump(entry.get("observation_ids")), entry.get("rule_or_mechanism"),
                entry.get("inference"), dump(entry.get("counterevidence_ids")), entry.get("status", "open"),
                entry.get("reviewer"), entry.get("reviewed_at"), entry.get("next_action")))
        for discrepancy in casefile.get("discrepancies", []):
            kind = discrepancy.get("type", "unclassified")
            message = discrepancy.get("summary") or discrepancy.get("message") or "Discrepancy recorded"
            disposition = discrepancy.get("status", "open")
            rationale = discrepancy.get("innocence_supporting") or discrepancy.get("routing_rationale") or "Review the source passage and the governing record."
            recommended_desks = []
            if discrepancy.get("is_exculpatory"):
                recommended_desks = ["records-custodian", "counsel", "casefile-reviewer"]
            elif kind in {"contradiction", "timing-gap", "omission", "procedural-error"}:
                recommended_desks = ["records-custodian", "casefile-reviewer"]
            else:
                recommended_desks = ["casefile-reviewer"]
            connection.execute("INSERT OR REPLACE INTO discrepancies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                discrepancy["id"], casefile["case_id"], kind, discrepancy.get("severity", "medium"),
                message, disposition, dump(recommended_desks), rationale, discrepancy.get("next_action", ""),
                dump(discrepancy.get("observation_ids", [])), dump(discrepancy.get("source_ids", []))))
        for entry in casefile.get("audit_log", []):
            connection.execute("INSERT OR REPLACE INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                entry["id"], casefile["case_id"], entry["action"], entry.get("actor"), entry["timestamp"],
                entry.get("object_id"), entry.get("reason"), entry.get("previous_version")))
        for request in casefile.get("requests", []):
            connection.execute("INSERT OR REPLACE INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                request["id"], casefile["case_id"], request.get("jurisdiction"), request.get("custodian"),
                request["description"], request.get("status", "draft"), request.get("submitted_at"),
                request.get("deadline"), request.get("response_at"), request.get("denial_reason"),
                request.get("counsel_review")))
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize and import a Signal Ledger SQLite casefile.")
    parser.add_argument("casefile", type=Path, help="Casefile JSON document")
    parser.add_argument("--database", type=Path, default=Path("evidence/signal-ledger.sqlite"))
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    import_case(args.database, args.casefile)
    print(f"Imported {args.casefile} into {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
