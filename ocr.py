"""Local OCR fallback for scanned PDFs and images (png, jpg, tiff) (macOS Vision via tools/ocr_pdf.swift). Nothing leaves this computer.

OCR text is a derived copy keyed by the source file's SHA-256 and stored under evidence/ocr/.
The preserved original is never modified. OCR can misread characters, so facts taken from it
must be checked against the page image before they are relied on.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "tools" / "ocr_pdf.swift"
BINARY = ROOT / "evidence" / ".bin" / "ocr_pdf"
CACHE = ROOT / "evidence" / "ocr"
MAX_PAGES = 60


def _binary() -> Path | None:
    if BINARY.exists() and not (SOURCE.exists() and SOURCE.stat().st_mtime > BINARY.stat().st_mtime):
        return BINARY
    if not SOURCE.exists():
        return None
    try:
        BINARY.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(SOURCE), "-o", str(BINARY)], capture_output=True, timeout=300, check=True)
    except (OSError, subprocess.SubprocessError):
        pass  # keep using an older binary if one exists
    return BINARY if BINARY.exists() else None


def ocr_pages(path: Path) -> list[str]:
    """Return OCR text per page, or [] when OCR is unavailable or fails."""
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return []
    cached = CACHE / f"{digest}.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))["pages"]
        except (OSError, ValueError, KeyError):
            pass
    binary = _binary()
    if binary is None:
        return []
    try:
        result = subprocess.run([str(binary), str(path), str(MAX_PAGES)], capture_output=True, text=True, timeout=900)
        pages = [" ".join(page.split()) for page in json.loads(result.stdout)] if result.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    if any(pages):
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"sha256": digest, "method": "apple-vision-ocr", "pages": pages}), encoding="utf-8")
    return pages
