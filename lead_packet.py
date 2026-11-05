"""Build a self-contained, honest packet of leads for a lawyer, reporter, or agency.

Verified leads are kept apart from unverified ones, every source is re-hashed against the manifest at
build time, and the limits of the collection are stated up front.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import verification
from discrepancy_engine import load_flags
from request_queue import list_requests

LIMITS = [
    "This packet lists leads: places where public records disagree or leave a question open. A lead is not a finding of wrongdoing.",
    "Only the sources captured in this case file were searched. Archive searches are capped per catalog and cover two catalogs; absence of a record here does not mean it does not exist.",
    "Text read by OCR can be wrong. Any lead marked UNVERIFIED must be compared with the original page before anyone relies on it.",
    "Name matches are not identity matches. Nothing here links two people or entities without a confirming identifier unless the document itself says so.",
    "Each lead lists innocent explanations. Ask the responsible agency for its explanation before drawing conclusions.",
]
ORDER = ["verified", "corrected", "unsupported", "stale-check", "unverified-ocr", "unverified"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _custody(evidence_dir: Path) -> dict[str, dict]:
    """Re-hash every manifest-listed capture; maps sha256 -> capture details with a custody status."""
    found: dict[str, dict] = {}
    for manifest in sorted(evidence_dir.glob("*manifest*.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("status") != "collected" or not item.get("sha256"):
                continue
            raw = Path(item.get("raw_file", ""))
            raw = raw if raw.is_absolute() else evidence_dir.parent / raw
            state = "missing"
            if raw.is_file():
                state = "intact" if _sha256(raw) == item["sha256"] else "HASH MISMATCH"
            found.setdefault(item["sha256"], {"url": item.get("url", ""), "captured_at": item.get("captured_at", ""),
                                              "file": str(item.get("raw_file", "")), "sha256": item["sha256"], "custody": state})
    return found


def build_packet(evidence_dir: Path | str = "evidence") -> dict:
    evidence_dir = Path(evidence_dir)
    flags = load_flags(evidence_dir / "discrepancy-flags.json")
    open_flags = [f for f in flags if f.get("status", "open") == "open" and f.get("protection", "public") == "public"]
    withheld = sum(1 for f in flags if f.get("status", "open") == "open") - len(open_flags)
    custody = _custody(evidence_dir)
    leads = []
    for flag in open_flags:
        sources = []
        for fact in flag.get("facts", []):
            src = fact.get("source") or {}
            record = custody.get(src.get("sha256", ""), {})
            sources.append({"url": src.get("ref", ""), "sha256": src.get("sha256", ""), "captured_at": record.get("captured_at", ""),
                            "file": record.get("file", ""), "custody": record.get("custody", "not in manifest"),
                            "passage": fact.get("passage", "")})
        level = verification.verification_level(flag)
        leads.append({"id": flag["id"], "kind": flag.get("kind", ""), "message": flag.get("message", ""), "where": (flag.get("link") or {}).get("detail", ""),
                      "level": level, "level_text": verification.LEVEL_TEXT[level], "checks": flag.get("verifications", []),
                      "innocent_explanations": flag.get("innocent_explanations", []), "next_action": flag.get("next_action", ""), "sources": sources,
                      "detected_at": flag.get("detected_at", "")})
    leads.sort(key=lambda lead: (ORDER.index(lead["level"]), lead["kind"], lead["where"]))
    bad = [s for c in custody.values() for s in [c] if c["custody"] != "intact"]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "leads": leads, "withheld_non_public": withheld,
            "custody_problems": bad, "captures_checked": len(custody),
            "requests": [{"agency": r.get("agency", ""), "status": r.get("status", ""), "deadline": r.get("deadline", ""), "description": r.get("description", "")}
                         for r in list_requests(evidence_dir / "requests.json")]}


def render_packet(packet: dict) -> str:
    leads = packet["leads"]
    counts = {level: sum(1 for l in leads if l["level"] == level) for level in ORDER}
    lines = ["# Lead packet", "", f"Generated {packet['generated_at'][:19]} UTC.", "", "## Read this first", ""]
    lines += [f"- {text}" for text in LIMITS]
    lines += ["", "## Summary", "", f"- {len(leads)} open leads: " + ", ".join(f"{n} {verification.LEVEL_TEXT[k]}" for k, n in counts.items() if n) if leads else "- No open leads.",
              f"- Chain of custody: {packet['captures_checked']} captures re-hashed; "
              + ("all intact." if not packet["custody_problems"] else f"{len(packet['custody_problems'])} PROBLEM(S) listed at the end."),]
    if packet["withheld_non_public"]:
        lines.append(f"- {packet['withheld_non_public']} lead(s) not marked public were left out.")
    for level in ORDER:
        group = [l for l in leads if l["level"] == level]
        if not group:
            continue
        lines += ["", f"## {verification.LEVEL_TEXT[level]} ({len(group)})", ""]
        for lead in group:
            lines += [f"### {lead['message']}", f"- Lead ID: `{lead['id']}`  |  Meeting/item: {lead['where']}  |  Type: {lead['kind']}"]
            for check in lead["checks"]:
                lines.append(f"- Check: {check['result']} by {check['reviewer']} on {check['verified_at'][:10]} via {check['method']}"
                             + (f", page {check['page']}" if check["page"] else "") + f". {check['note']}"
                             + (f" Correction: {check['corrected_text']}" if check["corrected_text"] else "")
                             + (f" Counter-evidence: {check['counter_evidence']}" if check["counter_evidence"] else ""))
            for src in lead["sources"]:
                lines += [f"- Source: {src['url']}", f"  - Captured {src['captured_at'][:19] or 'unknown'}; file `{src['file'] or 'n/a'}`; SHA-256 `{src['sha256'] or 'n/a'}`; custody: {src['custody']}",
                          f"  - Passage: \"{' '.join(src['passage'].split())}\""]
            lines += ["- Possible innocent explanations: " + ("; ".join(lead["innocent_explanations"]) or "none recorded"), f"- Next step: {lead['next_action']}", ""]
    if packet["requests"]:
        lines += ["", "## Records requests", ""]
        lines += [f"- [{r['status']}] {r['agency']}" + (f" (due {r['deadline']})" if r["deadline"] else "") + f": {r['description'][:160]}" for r in packet["requests"]]
    if packet["custody_problems"]:
        lines += ["", "## Custody problems", ""] + [f"- {p['custody']}: {p['url']} (`{p['sha256']}`)" for p in packet["custody_problems"]]
    return "\n".join(lines) + "\n"


def write_packet(evidence_dir: Path | str = "evidence") -> Path:
    evidence_dir = Path(evidence_dir)
    packet = build_packet(evidence_dir)
    out = evidence_dir / "lead-packet.md"
    out.write_text(render_packet(packet), encoding="utf-8")
    (evidence_dir / "lead-packet.json").write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(write_packet())
