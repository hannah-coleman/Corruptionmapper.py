#!/usr/bin/env python3
"""Build a local full-text index from collector and discovery manifests."""
from __future__ import annotations

import argparse
import json
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def extract_text(path: Path, content_type: str) -> str:
    if content_type != "text/html":
        return ""
    parser = TextParser()
    parser.feed(path.read_bytes().decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def title_for(item: dict, raw_file: Path) -> str:
    if item.get("title"):
        return str(item["title"])
    parsed = urlparse(item.get("url", ""))
    return parsed.path.rstrip("/").split("/")[-1] or parsed.netloc or raw_file.name


def main() -> int:
    parser = argparse.ArgumentParser(description="Index collected public evidence for local search.")
    parser.add_argument("manifest", type=Path, nargs="+", help="JSONL collector/discovery manifest files")
    parser.add_argument("--database", type=Path, default=Path("evidence/search.sqlite"))
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(args.database)
    connection.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(url, title, content, source_family, captured_at, raw_file, sha256)")
    connection.execute("DELETE FROM documents")
    indexed = 0
    try:
        for manifest_path in args.manifest:
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("status") != "collected" or not item.get("raw_file"):
                    continue
                raw_file = Path(item["raw_file"])
                content = extract_text(raw_file, item.get("content_type", ""))
                connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", (
                    item.get("url", ""), title_for(item, raw_file), content,
                    item.get("source_family", "unclassified"), item.get("captured_at", ""),
                    str(raw_file), item.get("sha256", "")))
                indexed += 1
        connection.commit()
    finally:
        connection.close()
    print(json.dumps({"indexed": indexed, "database": str(args.database)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
