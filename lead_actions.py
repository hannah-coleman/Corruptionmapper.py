"""Turn open leads into neutral records-request drafts and a manual verification checklist.

Nothing here contacts any agency. Requests are saved as drafts for the researcher to review and
submit; checklist items cover sources that block automated access (for example the Secretary of
State's business search), which must be searched by hand and the result saved with the upload form.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import autopopulate
import network_report as nr
from request_queue import add_request, list_requests

LAW = "Arkansas Freedom of Information Act, Ark. Code Ann. § 25-19-101 et seq."
CLERK = "City Clerk, City of Paragould"
FOOTER = ("Please provide electronic copies where available. If any part is withheld, please identify the exemption relied on "
          "and release the remainder. Please tell me in advance if copying costs will exceed an amount I should approve.")
LOOKUPS = {
    "business": "Arkansas Secretary of State business entity search: https://sos-corp-search.ark.org/ (blocks automated tools; search by hand and save the result page or PDF)",
    "property": "Greene County Assessor and Circuit Clerk (land records); also https://arcountydata.com/ if its terms permit your use",
    "ethics": "Arkansas Ethics Commission: https://www.arkansasethics.com/ (campaign finance and statements of financial interest)",
    "courts": "Arkansas CourtConnect: https://caseinfo.arcourts.gov/ (informational only; confirm with the clerk before relying on a docket)",
    "fec": "FEC: https://www.fec.gov/data/ (federal contributions; the app collects these when FEC_API_KEY is set)",
}


def _dates(flags: list[dict], kind: str) -> list[str]:
    return sorted({str((f.get("link") or {}).get("detail", ""))[:10] for f in flags if f.get("kind") == kind and (f.get("link") or {}).get("detail")})


def request_drafts(flags: list[dict]) -> list[dict]:
    open_flags = [f for f in flags if f.get("status", "open") == "open"]
    drafts = []

    def add(description: str, basis: str) -> None:
        drafts.append({
            "agency": CLERK, "law": LAW, "description": description, "basis": basis,
            "request_text": f"Under the {LAW}, I request copies of the following public records: {description} {FOOTER}",
        })

    missing = _dates(open_flags, "no-minutes")
    if missing:
        add(f"The approved minutes of the City Council meetings held on {', '.join(missing)}, and the agenda packets for those meetings.",
            "Agendas were collected for these meetings but no minutes, although later minutes exist.")
    tallies = _dates(open_flags, "vote-tally")
    if tallies:
        add(f"The signed minutes and any audio or video recording of the City Council meetings held on {', '.join(tallies)}, including the recorded roll-call votes.",
            "Announced vote tallies differ from the roll calls printed in the collected minutes.")
    gaps = [f for f in open_flags if f.get("kind") == "instrument-gap"]
    if gaps:
        add("The 2026 ordinance and resolution registers (or equivalent log) listing each ordinance and resolution number, its title, date and disposition, including numbers that were assigned but not adopted.",
            "Some ordinance and resolution numbers appear in no collected minutes.")
    agenda_only = defaultdict(set)
    for flag in open_flags:
        match = nr._PROPERTY.search(str(flag.get("message", "")))
        if flag.get("kind") == "agenda-only" and match:
            agenda_only[match.group(1).strip().rstrip(".")].add(str((flag.get("link") or {}).get("detail", ""))[:10])
    if agenda_only:
        listing = "; ".join(f"{address} (agenda of {', '.join(sorted(d))})" for address, d in sorted(agenda_only.items()))
        add(f"For each of these properties listed on City Council agendas for condemnation or lien action, the resolution or order adopted, the council action taken (including tabling or withdrawal), notices sent to the owner, and any related inspection reports: {listing}.",
            "Properties appear on agendas but are not described in the corresponding minutes.")
    return drafts


def policy_request(agency: str) -> dict:
    """Neutral draft asking an agency for its written policies. Not sent by the app."""
    agency = " ".join(str(agency).split())
    if not agency:
        raise ValueError("Enter the agency name.")
    description = ("The agency's current written policies, general orders or standard operating procedures on: arrests and booking, use of force and "
                   "its documentation, searches and seizures, vehicle and pedestrian stops, report writing, evidence handling, and complaint intake; "
                   "with the effective date and revision history of each, and any earlier versions in force since January 1 of the year in question.")
    return {"agency": agency, "law": LAW, "description": description, "basis": "Written policies are needed to compare against records entered for a case.",
            "request_text": f"Under the {LAW}, I request copies of the following public records: {description} {FOOTER}"}


def verification_checklist(net: dict) -> list[dict]:
    items = []
    for edge in net["edges"]:
        if edge["relation"] == "stated they represent":
            items.append({"subject": edge["target"], "why": f"{edge['source']} said they represent it before the council.",
                          "lookups": ["business", "ethics", "courts"], "record": "Entity ID, status, registered agent, officers, address, formation date"})
    for owner, props in sorted(net.get("owners", {}).items()):
        items.append({"subject": owner, "why": f"Named as owner of {', '.join(a.title() for a in sorted(props))} on council agendas.",
                      "lookups": ["business", "property", "courts"], "record": "Entity ID, registered agent, officers, address, other properties owned"})
    for name, person in sorted(net["people"].items()):
        if person["kind"] == "council member":
            items.append({"subject": name, "why": "Council member: compare declared interests and donors with items moved, seconded or abstained on.",
                          "lookups": ["ethics", "fec", "property"], "record": "Declared interests, donors, dates; note common-name matches separately"})
    return items


def render_checklist(items: list[dict]) -> str:
    lines = ["# Manual verification checklist", "",
             "Search each source yourself, save the result (page, PDF or screenshot) with *Preserve local file* in the app so it is hashed and dated, and record only what the source shows. "
             "A name match is not an identity match: confirm with address, middle name or filing number before linking anyone.", ""]
    for item in items:
        lines += [f"## {item['subject']}", f"- Why: {item['why']}", f"- Record: {item['record']}"]
        lines += [f"- Where: {LOOKUPS[key]}" for key in item["lookups"]]
        lines += ["- [ ] Searched and saved   - [ ] Identity confirmed   - [ ] Contrary evidence noted", ""]
    return "\n".join(lines)


def run(evidence_dir: Path | str = "evidence") -> dict:
    evidence_dir = Path(evidence_dir)
    captures = autopopulate.load_captures(evidence_dir)
    captures = captures[0] if isinstance(captures, tuple) else captures
    flags_path = evidence_dir / "discrepancy-flags.json"
    data = json.loads(flags_path.read_text(encoding="utf-8")) if flags_path.exists() else []
    flags = data if isinstance(data, list) else data.get("flags", [])
    queue = evidence_dir / "requests.json"
    known = {re.sub(r"\s+", " ", r.get("description", "")) for r in list_requests(queue)}
    added = []
    for draft in request_drafts(flags):
        if re.sub(r"\s+", " ", draft["description"]) not in known:
            added.append(add_request(queue, draft)["id"])
    checklist = render_checklist(verification_checklist(nr.build_network(captures)))
    (evidence_dir / "verification-checklist.md").write_text(checklist, encoding="utf-8")
    return {"draft_requests_added": len(added), "checklist": str(evidence_dir / "verification-checklist.md")}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
