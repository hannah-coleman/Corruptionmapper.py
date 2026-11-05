"""Human verification of leads against the original record.

A lead extracted by software (especially from OCR) is not usable until a person has compared it with
the original page, recording, or an agency's answer. Each check is stored with who did it, when, how,
and a fingerprint of the text that was checked, so a later re-extraction that changes the lead
automatically drops it back to unverified.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from discrepancy_engine import _write, load_flags

METHODS = {
    "page-image": "Compared with the page image or original PDF",
    "original-record": "Compared with the official original (clerk's file, certified copy)",
    "recording": "Compared with an audio or video recording",
    "agency-response": "Confirmed in a written response from the agency",
}
RESULTS = {
    "matches": "The record says what the lead says",
    "corrected": "The record differs from the extracted text (describe the correction)",
    "not-found": "The cited record does not support the lead",
}


def fingerprint(flag: dict) -> str:
    material = [str(flag.get("message", ""))] + sorted(str(f.get("passage", "")) for f in flag.get("facts", []))
    return hashlib.sha256(json.dumps(material).encode("utf-8")).hexdigest()[:16]


def verify_flag(path: Path | str, flag_id: str, check: dict) -> dict:
    method = str(check.get("method", "")).strip()
    result = str(check.get("result", "")).strip()
    reviewer = str(check.get("reviewer", "")).strip()
    note = str(check.get("note", "")).strip()
    if method not in METHODS:
        raise ValueError(f"Method must be one of: {', '.join(METHODS)}.")
    if result not in RESULTS:
        raise ValueError(f"Result must be one of: {', '.join(RESULTS)}.")
    if not reviewer or not note:
        raise ValueError("A reviewer name and a note describing exactly what you compared are required.")
    if result == "corrected" and not str(check.get("corrected_text", "")).strip():
        raise ValueError("Enter the corrected text exactly as it appears in the record.")
    flags = load_flags(path)
    for flag in flags:
        if flag["id"] != flag_id:
            continue
        flag.setdefault("verifications", []).append({
            "method": method, "result": result, "reviewer": reviewer, "note": note,
            "page": str(check.get("page", "")).strip(), "corrected_text": str(check.get("corrected_text", "")).strip(),
            "counter_evidence": str(check.get("counter_evidence", "")).strip(),
            "checked_text_fingerprint": fingerprint(flag),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        })
        _write(path, flags)
        return flag
    raise ValueError("Lead not found.")


def verification_level(flag: dict) -> str:
    """verified | corrected | unsupported | stale-check | unverified-ocr | unverified"""
    checks = flag.get("verifications") or []
    if checks:
        last = checks[-1]
        if last["checked_text_fingerprint"] != fingerprint(flag):
            return "stale-check"
        return {"matches": "verified", "corrected": "corrected", "not-found": "unsupported"}[last["result"]]
    return "unverified-ocr" if (flag.get("vector") or {}).get("text_method") == "ocr" else "unverified"


LEVEL_TEXT = {
    "verified": "Verified against the original record",
    "corrected": "Extraction was wrong; see the correction",
    "unsupported": "Not supported by the cited record",
    "stale-check": "Text changed since it was checked; re-verify",
    "unverified-ocr": "UNVERIFIED (read by OCR; check the page image)",
    "unverified": "UNVERIFIED (not yet compared with the original)",
}


def summary(flags: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for flag in flags:
        if flag.get("status", "open") == "open":
            level = verification_level(flag)
            counts[level] = counts.get(level, 0) + 1
    return counts
