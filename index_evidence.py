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


MAX_PDF_PAGES = 300


IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".tif": "image/tiff", ".tiff": "image/tiff"}
OFFICE_TYPES = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_OFFICE_PART_BYTES = 50_000_000
_PAGE_CACHE: dict[tuple, list[str]] = {}


def extract_pdf_pages(path: Path) -> list[str]:
    """Pages of text for a PDF; each unchanged file is parsed once per process, however many stages ask."""
    try:
        stat = path.stat()
    except OSError:
        return _extract_pdf_pages(path)
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _PAGE_CACHE:
        if len(_PAGE_CACHE) > 600:
            _PAGE_CACHE.clear()
        _PAGE_CACHE[key] = _extract_pdf_pages(path)
    return list(_PAGE_CACHE[key])


def extract_image_pages(path: Path) -> list[str]:
    from ocr import ocr_pages
    return ocr_pages(path)[:1]


def _xml_text(data: bytes, tags: tuple[str, ...], break_tags: tuple[str, ...]) -> str:
    import xml.etree.ElementTree as ET
    parts: list[str] = []
    for element in ET.fromstring(data).iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name in tags and element.text:
            parts.append(element.text)
        elif name in break_tags:
            parts.append("\n")
    return "".join(parts)


def extract_office_pages(path: Path) -> list[str]:
    """Text of a .docx (one page) or .xlsx (one page per sheet). Read-only; formulas are not evaluated."""
    import xml.etree.ElementTree as ET
    import zipfile
    try:
        with zipfile.ZipFile(path) as archive:
            def read(name: str) -> bytes:
                info = archive.getinfo(name)
                if info.file_size > MAX_OFFICE_PART_BYTES:
                    raise ValueError("Office file part too large to read safely.")
                return archive.read(name)
            names = set(archive.namelist())
            if "word/document.xml" in names:
                text = _xml_text(read("word/document.xml"), ("t",), ("p", "br", "tab"))
                return [" ".join(text.split())]
            if "xl/workbook.xml" in names:
                shared: list[str] = []
                if "xl/sharedStrings.xml" in names:
                    for si in ET.fromstring(read("xl/sharedStrings.xml")):
                        shared.append("".join(t.text or "" for t in si.iter() if t.tag.rsplit("}", 1)[-1] == "t"))
                pages = []
                for sheet in sorted(n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")):
                    cells = []
                    for cell in ET.fromstring(read(sheet)).iter():
                        if cell.tag.rsplit("}", 1)[-1] != "c":
                            continue
                        value = next((c.text for c in cell if c.tag.rsplit("}", 1)[-1] in ("v", "t") and c.text), None)
                        inline = "".join(t.text or "" for t in cell.iter() if t.tag.rsplit("}", 1)[-1] == "t")
                        if cell.get("t") == "s" and value is not None and value.isdigit() and int(value) < len(shared):
                            value = shared[int(value)]
                        cells.append(inline or value or "")
                    pages.append(" ".join(c for c in cells if c))
                return pages
    except (zipfile.BadZipFile, ValueError, KeyError, ET.ParseError):
        return []
    return []


def _extract_pdf_pages(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [" ".join((page.extract_text() or "").split()) for page in reader.pages[:MAX_PDF_PAGES]]
    except Exception:
        pages = []
    if not any(pages):
        from ocr import ocr_pages
        pages = ocr_pages(path)[:MAX_PDF_PAGES]
    return pages


def extract_pdf_text(path: Path) -> str:
    return " ".join(extract_pdf_pages(path)).strip()


def extract_html_text(path: Path) -> str:
    parser = TextParser()
    parser.feed(path.read_bytes().decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def extract_text(path: Path, content_type: str) -> str:
    if content_type == "application/pdf":
        return extract_pdf_text(path)
    if content_type == "text/plain":
        return " ".join(path.read_text(encoding="utf-8", errors="replace").split())
    if content_type in set(IMAGE_TYPES.values()):
        return " ".join(extract_image_pages(path)).strip()
    if content_type in set(OFFICE_TYPES.values()):
        return " ".join(extract_office_pages(path)).strip()
    if content_type != "text/html":
        return ""
    return extract_html_text(path)


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
    connection.execute("DROP TABLE IF EXISTS documents")
    connection.execute("CREATE VIRTUAL TABLE documents USING fts5(url, title, content, source_family, captured_at, raw_file, sha256, content_type)")
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
                connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                    item.get("url", ""), title_for(item, raw_file), content,
                    item.get("source_family", "unclassified"), item.get("captured_at", ""),
                    str(raw_file), item.get("sha256", ""), item.get("content_type", "")))
                indexed += 1
        connection.commit()
    finally:
        connection.close()
    print(json.dumps({"indexed": indexed, "database": str(args.database)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
