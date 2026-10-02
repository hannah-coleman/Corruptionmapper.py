"""Suggest which agencies to send public-records requests to, and for which records.

Suggestions come from two lawful inputs only: the approved source registry and text
already captured from public pages. Nothing here names or accuses a person; it lists
record sets an agency is likely to hold that the public capture does not contain.
"""
from __future__ import annotations

import re
from typing import Any

from records_gap_planner import GapPlanner

ARKANSAS_FOIA = "Arkansas Freedom of Information Act (Ark. Code Ann. § 25-19-101 et seq.)"
FEDERAL_FOIA = "Federal Freedom of Information Act (5 U.S.C. § 552)"
COURT_RULE = "Court records access rules (Arkansas Supreme Court Administrative Order No. 19), not FOIA"
LAW_NOTE = "Arkansas FOIA gives its access right to Arkansas citizens. Verify current rules, fees, and response deadlines with counsel."

# Pages that only hold navigation, accounts, or generic listings say nothing about specific records.
NON_SUBSTANTIVE_URL = re.compile(r"/(myaccount|login|search|profilecreate|calendar)", re.IGNORECASE)
# A keyword on most of a site's pages is menu/footer text, not a signal (applies once there are enough pages to judge).
BOILERPLATE_RATIO = 0.5
MIN_PAGES_FOR_RATIO = 5

PURPOSE = "a public-interest review of how public funds, decisions, and procedures are documented"

BASELINES: dict[str, list[tuple[str, str]]] = {
    "government": [
        ("meeting agendas, minutes, attachments, and recordings", "Shows what was decided, who voted, and what documents were before the body."),
        ("contracts, bids, scoring sheets, awards, and amendments", "Establishes how vendors were selected and what was agreed."),
        ("payment and vendor registers", "Connects awarded contracts to actual public money paid out."),
        ("conflict-of-interest disclosures and recusal records", "Documents whether disclosure and recusal procedures were followed."),
        ("budget amendments and appropriation ordinances", "Shows how funds were moved or authorized."),
    ],
    "law-enforcement": [
        ("written policies, general orders, and training standards", "Identifies the standards conduct is measured against."),
        ("grant, equipment-purchase, and memorandum-of-understanding records", "Documents outside funding and inter-agency agreements."),
        ("complaint and disciplinary outcome summaries (releasable portions)", "Shows whether complaints reach documented outcomes; request segregable non-exempt portions only."),
    ],
    "business": [
        ("entity formation filings, registered-agent history, and annual reports", "Establishes who is behind an entity and when it changed."),
    ],
    "judicial": [
        ("docket and filing index for a defined matter", "Court records are requested from the clerk; filings are not findings."),
    ],
    "political": [
        ("campaign-finance and ethics filings for a defined period", "Shows reported contributions, expenditures, and disclosures."),
    ],
    "oversight": [
        ("published audit reports and agency responses", "Shows findings already issued and management responses."),
    ],
    "federal": [
        ("records held by the specific federal agency responsible for a defined program or grant", "Federal FOIA applies only to federal agencies; name the agency and program."),
    ],
}


def _law_for(entry: dict) -> str:
    if entry.get("category") == "judicial":
        return COURT_RULE
    if entry.get("jurisdiction") == "federal":
        return FEDERAL_FOIA
    return ARKANSAS_FOIA


def _agency_for_host(host: str, registry: list[dict]) -> str | None:
    host = host.lower()
    for entry in registry:
        if host in [h.lower() for h in entry.get("hosts", [])]:
            return entry["id"]
    return None


def _snippet(text: str, keyword: str, width: int = 90) -> str:
    match = re.search(re.escape(keyword), text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - width)
    return " ".join(text[start:match.end() + width].split())


def build_plan(registry: list[dict], documents: list[dict], requests: list[dict], time_range: str = "the relevant period") -> list[dict]:
    planner = GapPlanner()
    from urllib.parse import urlparse

    docs_by_agency: dict[str, list[dict]] = {}
    for doc in documents:
        agency_id = _agency_for_host(urlparse(str(doc.get("url", ""))).hostname or "", registry)
        if agency_id:
            docs_by_agency.setdefault(agency_id, []).append(doc)

    plan = []
    for entry in registry:
        if entry.get("access") == "restricted" or entry.get("status") == "do-not-bulk-collect":
            continue
        docs = docs_by_agency.get(entry["id"], [])
        existing = " ".join(str(r.get("description", "")).lower() for r in requests if entry["label"].lower() in str(r.get("agency", "")).lower())
        suggestions: list[dict[str, Any]] = []
        seen: set[str] = set()

        for keyword, config in planner.KEYWORD_MAP.items():
            substantive = [doc for doc in docs if not NON_SUBSTANTIVE_URL.search(str(doc.get("url", "")))]
            hits = [doc for doc in substantive if keyword in str(doc.get("content", "")).lower()]
            if not hits or config["document_type"] in seen:
                continue
            if len(substantive) >= MIN_PAGES_FOR_RATIO and len(hits) / len(substantive) > BOILERPLATE_RATIO:
                continue
            seen.add(config["document_type"])
            suggestions.append({
                "document_type": config["document_type"],
                "basis": "evidence-indicated",
                "rationale": f"{len(hits)} captured page(s) from this source mention '{keyword}', but the underlying records are not part of the capture.",
                "evidence": [{"url": doc["url"], "excerpt": _snippet(str(doc.get("content", "")), keyword)} for doc in hits[:3]],
                "questions": config["questions"],
            })

        for document_type, rationale in BASELINES.get(entry.get("category", ""), []):
            if document_type in seen:
                continue
            suggestions.append({"document_type": document_type, "basis": "baseline", "rationale": rationale, "evidence": [], "questions": []})

        for suggestion in suggestions:
            draft = planner.draft_foia_request(entry["label"], [suggestion["document_type"]], PURPOSE, time_range)
            suggestion["draft"] = {"request_text": draft.request_text, "notes": draft.notes}
            suggestion["already_requested"] = suggestion["document_type"].lower() in existing

        plan.append({
            "agency_id": entry["id"],
            "agency": entry["label"],
            "jurisdiction": entry.get("jurisdiction"),
            "category": entry.get("category"),
            "route": entry.get("request_route"),
            "law": _law_for(entry),
            "law_note": LAW_NOTE if _law_for(entry) == ARKANSAS_FOIA else "",
            "source_status": entry.get("status"),
            "captured_pages": len(docs),
            "suggestions": sorted(suggestions, key=lambda s: (s["basis"] != "evidence-indicated", s["document_type"])),
        })
    return sorted(plan, key=lambda item: (-sum(s["basis"] == "evidence-indicated" for s in item["suggestions"]), item["agency"]))
