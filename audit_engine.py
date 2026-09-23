#!/usr/bin/env python3
"""Find reviewable discrepancies in a structured, source-backed case file."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("The input must be a JSON array of records.")
    required = {"id", "subject", "claim", "source_url"}
    for record in data:
        missing = required - record.keys()
        if missing:
            raise ValueError(f"Record {record.get('id', '<unknown>')} missing: {', '.join(sorted(missing))}")
    return data


def routing_for(kind: str) -> tuple[list[str], str]:
    routes = {
        "contradiction": (["counsel", "records-custodian"], "Compare the governing record and preserve both versions before drawing a conclusion."),
        "missing-metadata": (["casefile-reviewer", "records-custodian"], "Complete provenance or document why the field cannot be obtained."),
        "duplicate-source": (["casefile-reviewer"], "Check source independence before counting corroboration."),
        "timeline-collision": (["casefile-reviewer", "records-custodian"], "Compare timestamps, versions, and applicable deadlines."),
    }
    return routes.get(kind, (["casefile-reviewer"], "Review the source and assign the appropriate specialist."))


def lawful_actions_for(kind: str) -> list[str]:
    actions = {
        "contradiction": ["Preserve both source passages", "Identify the governing rule or version", "Request the missing or corrected public record", "Ask counsel whether formal preservation is appropriate"],
        "missing-metadata": ["Check the issuing body's public index", "Request the missing metadata from the records custodian", "Record the access limitation if unavailable"],
        "duplicate-source": ["Locate the earliest or primary source", "Mark derivative copies as non-independent", "Seek an independent public record or on-record response"],
        "timeline-collision": ["Compare timestamps and time zones", "Request the relevant meeting, filing, or transaction record", "Ask counsel to review deadline or preservation implications"],
    }
    return actions.get(kind, ["Review the public source", "Identify the lawful custodian", "Document a narrow records request", "Route unresolved legal issues to counsel"])


def flag(kind: str, severity: str, message: str, records: list[dict]) -> dict:
    desks, rationale = routing_for(kind)
    return {"id": hashlib.sha256((kind + message).encode()).hexdigest()[:12], "kind": kind,
            "severity": severity, "message": message, "record_ids": [r["id"] for r in records],
            "source_urls": sorted({r["source_url"] for r in records}), "recommended_desks": desks,
            "routing_rationale": rationale, "lawful_next_actions": lawful_actions_for(kind),
            "disposition": "unreviewed", "next_action": ""}


def analyze(records: list[dict]) -> list[dict]:
    flags: list[dict] = []
    by_subject_field: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)
    by_url: defaultdict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_url[record["source_url"]].append(record)
        if record.get("field"):
            by_subject_field[(record["subject"].lower(), record["field"].lower())].append(record)
        for field in ("agency", "record_type", "published_at", "captured_at"):
            if not record.get(field):
                flags.append(flag("missing-metadata", "medium", f"{record['id']} has no {field}.", [record]))

    for (subject, field), group in by_subject_field.items():
        values = {str(record.get("value", "")).strip().lower() for record in group}
        if len(values) > 1:
            flags.append(flag("contradiction", "high", f"Sources give conflicting {field} values for {subject}: " + "; ".join(sorted(values)), group))

    for url, group in by_url.items():
        claims = {record["claim"].strip().lower() for record in group}
        if len(group) > 1 and len(claims) == 1:
            flags.append(flag("duplicate-source", "low", f"{len(group)} records rely on the same source URL; do not count them as independent corroboration.", group))

    by_subject: defaultdict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_subject[record["subject"].lower()].append(record)
    for subject, group in by_subject.items():
        dates = [r.get("event_date") for r in group if r.get("event_date")]
        if len(dates) != len(set(dates)) and len(dates) > 1:
            flags.append(flag("timeline-collision", "medium", f"Multiple records place events for {subject} on the same date; compare times and document versions.", group))

    return flags


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a source-backed case file for discrepancies.")
    parser.add_argument("records", type=Path, help="JSON array of normalized evidence records")
    parser.add_argument("--output", type=Path, default=Path("evidence/flags.json"))
    args = parser.parse_args()
    records = load_records(args.records)
    flags = analyze(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(flags, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "flags": len(flags), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
