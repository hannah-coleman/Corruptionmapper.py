"""Turn the collected records into a prioritized investigation checklist.

Only public officials and organizations named in collected public records get lookups, and every
lookup points to a public source. Each task says what to record and what would rule the lead out.
No private individuals, no logins, no scraping of platforms.
"""
from __future__ import annotations

SOS = "https://www.sos.arkansas.gov/"
COURTS = "https://caseinfo.arcourts.gov/"
ETHICS = "https://www.arkansasethics.com/"
AUDITS = "https://www.arklegaudit.gov/reports/"
TRANSPARENCY = "https://transparency.arkansas.gov/"
FEC = "https://www.fec.gov/data/"


def build_plan(net: dict, flags: list[dict]) -> list[dict]:
    tasks = []
    open_flags = [f for f in flags if f.get("status", "open") == "open"]
    kinds = {}
    for flag in open_flags:
        kinds.setdefault(flag.get("kind"), []).append(flag)
    if kinds.get("no-minutes"):
        tasks.append({"priority": 1, "task": f"Request the missing minutes ({len(kinds['no-minutes'])} meetings) from the City Clerk; use the request queue so the response deadline is tracked.",
                      "where": "City Clerk, Paragould", "record": "Date requested, who answered, what was provided", "rules_out": "Minutes posted elsewhere or the meeting was not held"})
    if kinds.get("vote-tally"):
        tasks.append({"priority": 1, "task": f"Check the {len(kinds['vote-tally'])} roll-call vs. announced-tally leads against the page image, then ask the Clerk for the recording or signed minutes if they still differ.",
                      "where": "Evidence index (page image), City Clerk", "record": "Corrected tally or confirmation of the discrepancy", "rules_out": "OCR misread; abstention counted differently"})
    if kinds.get("agenda-only"):
        tasks.append({"priority": 2, "task": f"For the {len(kinds['agenda-only'])} agenda items missing from minutes (mostly condemnation properties), check Greene County property records and the next meeting's minutes to see whether each was tabled, completed or dropped.",
                      "where": "Greene County Assessor/Clerk; later Agenda Center minutes", "record": "Disposition of each property", "rules_out": "Tabled or moved to another meeting"})

    outsiders = sorted({e["source"] for e in net["edges"] if e["relation"] in {"addressed the council", "stated they represent"}})
    orgs = sorted({e["target"] for e in net["edges"] if e["relation"] == "stated they represent"})
    for org in orgs:
        tasks.append({"priority": 2, "task": f"Look up '{org}' in Secretary of State business filings: registered agent, officers, formation date, other entities at the same address.",
                      "where": SOS, "record": "Entity ID, agent, officers, address (cite the page and date)", "rules_out": "Ordinary national lender or local nonprofit with no tie to the item"})
    for name in outsiders:
        tasks.append({"priority": 3, "task": f"Search the court index for '{name}' only if they appeared on a contested item; note case numbers, not conclusions.",
                      "where": COURTS, "record": "Case number, court, filing date", "rules_out": "Common name; different person"})

    members = sorted(p["label"] for p in net["people"].values() if p["kind"] == "council member")
    if members:
        tasks.append({"priority": 2, "task": "For each council member, check statements of financial interest, gift and campaign filings: " + ", ".join(members) + ". Compare declared interests with the items they moved, seconded or abstained on.",
                      "where": ETHICS + " and " + FEC, "record": "Declared interests, donors, dates", "rules_out": "No overlap with items voted on"})
        tasks.append({"priority": 3, "task": "Find each member's and the mayor's official public pages (city website, official campaign page or verified account). Save the exact words and date with the 'Add a public statement' form; the app compares figures and measure numbers with the records.",
                      "where": "Their own official public accounts, found through the city website", "record": "Link, date, quote", "rules_out": "Figure was rounded or from a record not yet collected"})
    if net["awards"]:
        tasks.append({"priority": 2, "task": "Pick the largest local federal recipients and compare award amounts with what the city, county or school says it received and spent; also pull each recipient's state filing and Form 990 if it is a nonprofit.",
                      "where": TRANSPARENCY + " and USAspending in the report", "record": "Award ID, amount, recipient, matching local record", "rules_out": "Different fiscal year or pass-through funding"})
    tasks += [
        {"priority": 2, "task": "Read the newest Legislative Audit reports for Paragould, Greene County, the school district and the police department; log each finding and whether it was resolved.",
         "where": AUDITS, "record": "Finding number, amount, agency response", "rules_out": "Finding already corrected"},
        {"priority": 3, "task": "Child welfare: collect Arkansas DCFS annual reports and audit findings, and the public NamUs and NCMEC counts for Greene County; compare counts across sources.",
         "where": "Agency report pages (verify URL first), namus.nij.ojp.gov, missingkids.org", "record": "Counts, year, definitions used", "rules_out": "Different definitions of 'missing' between agencies"},
        {"priority": 3, "task": "Police: file Arkansas FOIA requests for use-of-force reports, complaint logs, discipline records and settlement payments; track them in the request queue.",
         "where": "Paragould Police and Greene County Sheriff records custodian", "record": "Request date, response, redactions", "rules_out": "Records exempt or non-existent"},
    ]
    return sorted(tasks, key=lambda t: t["priority"])


def render_plan(tasks: list[dict]) -> str:
    out = ["## Investigation plan (what to look up next)", "",
           "Public sources only, public officials and organizations named in the records. Record case numbers, filing dates and quotes, not conclusions.", ""]
    for i, t in enumerate(tasks, 1):
        out += [f"{i}. **[P{t['priority']}]** {t['task']}", f"   - Where: {t['where']}", f"   - Record: {t['record']}", f"   - Could rule it out: {t['rules_out']}"]
    return "\n".join(out) + "\n"
