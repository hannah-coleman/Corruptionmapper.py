#!/usr/bin/env python3
"""Import collected discovery manifest entries as reviewed source records."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from casefile_db import SCHEMA


def import_manifest(database: Path, case_id: str, manifest: Path) -> int:
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    imported = 0
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("status") != "collected":
                continue
            url = item["url"]
            source_id = f"discovery-{item.get('sha256', url)[:24]}"
            parsed = urlparse(url)
            title = item.get("title") or parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
            connection.execute("INSERT OR IGNORE INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                source_id, case_id, title, item.get("host", ""), url,
                "official-public-site", "public-download", "public", "public-graph", None,
                item.get("captured_at"), item.get("sha256"), item.get("content_type", "unknown"),
                json.dumps(["Discovery import is source-only; human review required."], sort_keys=True)))
            imported += 1
        connection.commit()
    finally:
        connection.close()
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import public discovery snapshots as source records.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--case-id", default="case-example-001")
    parser.add_argument("--database", type=Path, default=Path("evidence/signal-ledger.sqlite"))
    args = parser.parse_args()
    print(f"Imported {import_manifest(args.database, args.case_id, args.manifest)} source snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
