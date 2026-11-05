"""Build a cited relationship network and a plain-language lead report from collected public records.

Nothing here accuses anyone. A link means "these two names appear together in this document in this
way" and always carries the quoted passage and source. Counts are small, text may come from OCR, and
every pattern is a question to put to the record, not a conclusion about a person.
"""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import meeting_compare as mc
import verification
from investigation_guide import build_plan, render_plan
from claim_store import load_claims
from reference_register import load_references
from fact_sources import pages_for_file

_NAME = r"[A-Z][A-Za-z'’\-]+"
_MOTION = re.compile(
    rf"Motion[^.]{{0,200}}?(?:made|offered)\s+by\s+(?:Council\s+Member|Alderman|Mayor)\s+([A-Z]\s?[a-z'’\-]+)\s*;\s*second\s?ed\s+by\s+(?:Council\s+Member|Alderman|Mayor)\s+([A-Z]\s?[a-z'’\-]+)", re.IGNORECASE)
_APPEARS = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+((?:[A-Z][a-z]+\s+){1,2}[A-Z][a-z]+)\s+(?:was|were)\s+present\s+to\s+address", re.IGNORECASE)
_REPRESENTING = re.compile(r"\b((?:[A-Z][a-z]+\.?\s+){1,2}[A-Z][a-z]+),\s+representing\s+([A-Z][^.;,]{3,80})")
_AWARD = re.compile(r"Federal award (\S+) to (.+?): \$([\d,\.]+) awarded by (.+?), start date")
_OWNER = re.compile(
    r"located at (.{4,60}?) and is owned by ((?:[A-Z&][\w&'’\-]*\.?,?\s+){0,6}?(?:LLC|L\.L\.C\.|Inc|LP|Corp|Company|Properties|Trust)(?:,?\s+(?:LLC|Inc|LP|Corp))?)\b")
_STATE_RECIPIENT = re.compile(r"^(ARKANSAS DEPARTMENT|STATE OF ARKANSAS|ARKANSAS STATE (?!UNIVERSITY))", re.IGNORECASE)
_MAYOR = re.compile(r"\bMayor\s+([A-Z][a-z]+)")


def _canon_factory(names: list[str]):
    counts = Counter(names)
    canon = [n for n, c in counts.most_common() if c >= 5]

    def canon_name(raw: str) -> str:
        raw = re.sub(r"\s+", "", raw).capitalize()
        match = difflib.get_close_matches(raw, canon, n=1, cutoff=0.75)
        return match[0] if match else raw
    return canon_name


def _clean(name: str) -> str:
    return re.sub(r"^(?:Mr|Ms|Mrs|Dr)\.?\s+", "", " ".join(name.split()))


def _snippet(text: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - 120):end + 120]).strip()


def build_network(captures: list[dict]) -> dict:
    meetings = mc._load(captures)
    minutes = {k: d["minutes"] for k, d in meetings.items() if "minutes" in d}
    voters = [n for doc in minutes.values() for m in mc._ROLL.finditer(doc["text"]) for n, _ in mc._VOTER.findall(m.group(1))]
    canon = _canon_factory(voters)
    edges: dict[tuple, dict] = {}
    people: dict[str, dict] = {}

    def person(name: str, kind: str = "person") -> dict:
        return people.setdefault(name, {"label": name, "kind": kind, "meetings": set(), "votes": Counter()})

    def edge(a: str, b: str, relation: str, meeting: str, doc: dict, passage: str) -> None:
        key = (a, b, relation)
        item = edges.setdefault(key, {"source": a, "target": b, "relation": relation, "evidence": []})
        item["evidence"].append({"meeting": meeting, "passage": passage, "url": doc["url"], "ocr": doc["ocr"]})

    for meeting, doc in sorted(minutes.items()):
        text = doc["text"]
        for roll in mc._ROLL.finditer(text):
            for name, vote in mc._VOTER.findall(roll.group(1)):
                member = person(canon(name), "council member")
                member["meetings"].add(meeting)
                member["votes"][vote.lower()] += 1
                if vote.lower() in {"no", "nay"} or vote.lower().startswith("abstain"):
                    edge(canon(name), "Council vote", f"voted '{vote.lower()}'", meeting, doc, _snippet(text, roll.start(), roll.end()))
        for motion in _MOTION.finditer(text):
            first, second = canon(motion.group(1)), canon(motion.group(2))
            person(first, "council member"), person(second, "council member")
            if first != second:
                edge(first, second, "moved / seconded with", meeting, doc, _snippet(text, motion.start(), motion.end()))
        for match in _APPEARS.finditer(text):
            guest = person(_clean(match.group(1)), "appeared before council")
            guest["meetings"].add(meeting)
            edge(guest["label"], "City Council", "addressed the council", meeting, doc, _snippet(text, match.start(), match.end()))
        for match in _REPRESENTING.finditer(text):
            guest = person(_clean(match.group(1)), "appeared before council")
            org = " ".join(match.group(2).split())
            person(org, "organization")
            edge(guest["label"], org, "stated they represent", meeting, doc, _snippet(text, match.start(), match.end()))
        for match in _MAYOR.finditer(text):
            if match.group(1).lower() not in {"s", "of"}:
                person(f"Mayor {match.group(1)}", "mayor").setdefault("meetings", set()).add(meeting)

    awards = []
    for capture in captures:
        if "usaspending" not in capture["url"] or capture.get("content_type") != "text/plain":
            continue
        try:
            text = " ".join(pages_for_file(capture["path"], "text/plain"))
        except Exception:
            continue
        for match in _AWARD.finditer(text):
            awards.append({"award": match.group(1), "recipient": match.group(2), "amount": match.group(3), "agency": match.group(4), "url": capture["url"]})
    owners: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for meeting, docs in meetings.items():
        if "agenda" not in docs:
            continue
        for match in _OWNER.finditer(" ".join(docs["agenda"]["text"].split())):
            owners[match.group(2).strip().rstrip(",")][match.group(1).strip().lower()].add(meeting[:10])
    return {"people": people, "edges": list(edges.values()), "awards": awards, "meetings_read": len(minutes), "owners": owners}


def _bullets(rows: list[str]) -> str:
    return "\n".join(f"- {row}" for row in rows) or "- None found in the collected records."


def _suggested_questions(flags: list[dict]) -> list[dict]:
    questions = []
    seen = set()
    for flag in flags:
        if flag.get("status", "open") != "open":
            continue
        message = re.sub(r"\s+", " ", str(flag.get("message", ""))).strip().rstrip(".!?")
        if not message:
            continue
        question = f"What explains this record discrepancy: {message}?"
        key = question.casefold()
        if key in seen:
            continue
        seen.add(key)
        questions.append({
            "statement": question,
            "alternatives": flag.get("innocent_explanations", []),
            "next_test": flag.get("next_action", ""),
            "verification": verification.LEVEL_TEXT[verification.verification_level(flag)],
        })
    return questions


_PROPERTY = re.compile(r"property at (.+?) that the minutes never mention", re.IGNORECASE)


def _pattern_questions(net: dict, flags: list[dict]) -> list[dict]:
    """Questions built from patterns in the collected records; each names the records it came from."""
    questions = []

    def add(statement: str, alternatives: list[str], next_test: str, basis: str) -> None:
        questions.append({"statement": statement, "alternatives": alternatives, "next_test": next_test, "basis": basis})

    open_flags = [f for f in flags if f.get("status", "open") == "open"]
    by_address = defaultdict(set)
    for flag in open_flags:
        match = _PROPERTY.search(str(flag.get("message", "")))
        if match:
            by_address[" ".join(match.group(1).lower().rstrip(".").split())].add(str((flag.get("link") or {}).get("detail", ""))[:10])
    for address, dates in sorted(by_address.items()):
        if len(dates) > 1:
            add(f"Why did the property at {address.title()} appear on council agendas for {', '.join(sorted(dates))} without being described in the minutes, and what was finally decided?",
                ["It may have been tabled repeatedly while the owner made repairs.", "The minutes may record it under a different description."],
                "Ask the City Clerk for the disposition of this item at each meeting and check county records for liens or demolition.",
                "Same address flagged on more than one agenda.")

    agenda_only = [f for f in open_flags if f.get("kind") == "agenda-only"]
    if len(agenda_only) > 1:
        add(f"How many of the {len(agenda_only)} condemnation items listed on agendas but missing from minutes were actually acted on, and who owned those properties?",
            ["Items may have been tabled or withdrawn.", "Minutes may summarize several items together."],
            "Ask the City Clerk for the action taken on each; compare owners with county assessor and Secretary of State records.",
            f"{len(agenda_only)} agenda-only discrepancies.")

    tallies = [f for f in open_flags if f.get("kind") == "vote-tally"]
    if tallies:
        add(f"Do the signed minutes or recordings for the {len(tallies)} meetings where the announced tally differs from the roll call show a different vote, or only an OCR misreading?",
            ["OCR may have misread a name or vote.", "An abstention may have been counted differently."],
            "View each page image, then request the signed minutes and any recording.",
            f"{len(tallies)} vote-tally discrepancies.")

    for edge in net["edges"]:
        if edge["relation"] == "stated they represent":
            dates = ", ".join(sorted({x["meeting"][:10] for x in edge["evidence"]}))
            add(f"What was {edge['source']}'s stated relationship to {edge['target']} when addressing the council on {dates}, and does {edge['target']} have contracts, property or filings connected to the item discussed?",
                ["They may be an ordinary resident, lender, or nonprofit with no financial tie to the item."],
                "Check Secretary of State filings, county property records, campaign-finance filings, and the agenda item discussed.",
                "Outside party named in minutes.")

    dissent = defaultdict(list)
    for edge in net["edges"]:
        if edge["target"] == "Council vote" and edge["relation"] != "voted 'abstain'":
            dissent[edge["source"]].extend(x["meeting"][:10] for x in edge["evidence"])
    for member, dates in sorted(dissent.items()):
        add(f"What did {member} vote against on {', '.join(sorted(set(dates)))}, and did the minutes record a reason?",
            ["The vote may be routine and unrelated to money or conflicts."],
            "Read the motion and discussion on the page image; compare with how the same member voted on similar items.",
            "Recorded 'no' vote.")

    top = defaultdict(float)
    for award in net["awards"]:
        if award["recipient"].upper().startswith(("MULTIPLE RECIPIENTS", "REDACTED")) or _STATE_RECIPIENT.match(award["recipient"]):
            continue
        try:
            top[(award["recipient"], award["agency"], award["award"])] += float(award["amount"].replace(",", ""))
        except ValueError:
            continue
    for (recipient, agency, award_id), amount in sorted(top.items(), key=lambda kv: -kv[1])[:5]:
        add(f"Which local budget, minutes or contract records correspond to federal award {award_id} (${amount:,.0f} from {agency} to {recipient}), and was it spent as described?",
            ["Funds may pass through the state or span several fiscal years."],
            "Match the award to the recipient's budget, audit and local minutes; request payment records if absent.",
            "Largest Greene County federal awards.")
    for owner, properties in sorted(net.get("owners", {}).items()):
        addresses = sorted(properties)
        dates = sorted({d for ds in properties.values() for d in ds})
        subject = f"{owner}, named as owner of {', '.join(a.title() for a in addresses)} on condemnation or lien agenda items ({', '.join(dates)})"
        add(f"Who stands behind {subject}: what are its registered agent, officers and other properties, and does it connect to anyone who appeared before the council?",
            ["It may be an ordinary investor or lender with no tie to any official.", "A shared agent or address may only reflect a common filing service."],
            "Search the Secretary of State entity record, county assessor and deed records, and court filings; save the page and date of each result.",
            "Business owner named on agendas.")
    return questions


def render_report(captures: list[dict], flags: list[dict], gaps: list[str] | None = None) -> str:
    net = build_network(captures)
    people, edges = net["people"], net["edges"]
    lines = [
        "# Signal Ledger lead report", "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from {len(captures)} verified public captures "
        f"({net['meetings_read']} sets of council minutes read).", "",
        "**How to read this.** Everything below is a lead drawn from public records. A link means two names appear together in a document in a stated way; "
        "a discrepancy means two records do not agree. Neither is evidence of wrongdoing. Each item names its source so you can check it, and items read from scanned pages "
        "(OCR) may contain misread characters. Verify against the original before relying on anything here.", "",
        "**Verification status of open discrepancies:** " + (", ".join(f"{n} {verification.LEVEL_TEXT[k]}" for k, n in verification.summary(flags).items()) or "none open") + ".", ""]

    council = sorted((p for p in people.values() if p["kind"] == "council member"), key=lambda p: p["label"])
    lines += ["## Who appears and how often", "",
              _bullets([f"{p['label']}: present in {len(p['meetings'])} meetings; votes {dict(p['votes'])}" for p in council]), ""]

    pairs = Counter({(e["source"], e["target"]): len(e["evidence"]) for e in edges if e["relation"] == "moved / seconded with"})
    lines += ["## Who moves and seconds for whom", "",
              "Pairings that recur are normal in a small body; they matter only when paired with a conflict of interest or a one-sided pattern on contested items.", "",
              _bullets([f"{a} moved, {b} seconded: {n} times" for (a, b), n in pairs.most_common(10)]), ""]

    dissent = [e for e in edges if e["target"] == "Council vote"]
    lines += ["## Dissent and abstentions (verify each against the page image)", "",
              _bullets([f"{e['source']} {e['relation']} on {', '.join(sorted({x['meeting'][:10] for x in e['evidence']}))}" for e in dissent]), ""]

    outsiders = defaultdict(list)
    for e in edges:
        if e["relation"] in {"addressed the council", "stated they represent"}:
            outsiders[e["source"]].append(e)
    lines += ["## Outside parties who appeared before the council", "",
              _bullets([f"{name}: {'; '.join(sorted({e['relation'] + (' ' + e['target'] if e['target'] != 'City Council' else '') + ' (' + x['meeting'][:10] + ')' for e in es for x in e['evidence']}))}"
                        for name, es in sorted(outsiders.items())]), "",
              "Next step: check each name against Secretary of State business filings, county property records and campaign-finance filings for ties to the council item they addressed (manual upload if a source cannot be collected).", ""]

    by_recipient = defaultdict(float)
    for a in net["awards"]:
        if a["recipient"].upper().startswith(("MULTIPLE RECIPIENTS", "REDACTED")):
            continue
        try:
            by_recipient[(a["recipient"], a["agency"])] += float(a["amount"].replace(",", ""))
        except ValueError:
            continue
    lines += ["## Federal money flowing into Greene County (USAspending)", "",
              _bullets([f"{r} ← {ag}: ${amt:,.0f}" for (r, ag), amt in sorted(by_recipient.items(), key=lambda kv: -kv[1])[:15]]), ""]

    open_flags = [f for f in flags if f.get("status", "open") == "open"]
    lines += [f"## Where records disagree or are missing ({len(open_flags)} open leads)", ""]
    for flag in open_flags:
        lines.append(f"### {flag.get('kind', 'lead')}: {flag.get('message', '')}")
        for fact in flag.get("facts", [])[:2]:
            lines.append(f"> {re.sub(chr(10), ' ', str(fact.get('passage', '')))[:300]}  \n> Source: {(fact.get('source') or {}).get('ref', '')}")
        if flag.get("innocent_explanations"):
            lines.append("Rule out first: " + "; ".join(flag["innocent_explanations"]))
        if flag.get("next_action"):
            lines.append(f"Next step: {flag['next_action']}")
        lines.append("")

    lines.append(render_plan(build_plan(net, flags)))
    claims = load_claims("evidence/claims.json")
    suggested = _suggested_questions(flags)
    patterns = _pattern_questions(net, flags)
    lines += ["## Working narratives (plausibilities, not facts)", "",
              "### Questions drawn from patterns in the records", "",
              _bullets([f"[pattern question] {item['statement']} Basis: {item['basis']} Alternatives: {'; '.join(item['alternatives'])} Next test: {item['next_test']} Status: UNVERIFIED (built from extracted text; confirm on the original page)." for item in patterns]), "",
              "### Suggested questions from open discrepancies", "",
              _bullets([f"[suggested question] {item['statement']} - alternatives: {'; '.join(item['alternatives']) or 'none recorded'}; next test: {item['next_test'] or 'none recorded'}; status: {item['verification']}" for item in suggested]), "",
              "### Questions and narratives in the research ledger", "",
              _bullets([f"[{c.get('status')}] {c.get('statement')} - sources: {len(c.get('source_ids', []))}; alternatives: {'; '.join(c.get('alternative_explanations', [])) or 'none recorded'}; next test: {c.get('next_test') or 'none recorded'}" for c in claims]), ""]
    refs = load_references("evidence/references.json")
    lines += ["## Known controversies cited for reference (reported, not verified)", "",
              _bullets([f"{r.get('topic') or 'untitled'}: {r['summary']} ({r.get('outlet') or 'outlet unknown'}, {r.get('published') or 'undated'}) <{r['url']}>. Check against: {', '.join(r.get('records_to_check', [])) or 'not yet specified'}" for r in refs]), ""]
    lines += ["## What is missing from this picture", "",
              _bullets((gaps or []) + [
                  "No court dockets, business registrations, property records, campaign-finance filings (needs FEC key) or police/personnel records are in the collected set; these must be requested or uploaded.",
                  "Judges, prosecutors and attorneys appear only when named in collected documents; none have been collected from court sources.",
                  "Council relationships come from a small number of minutes; patterns will firm up or disappear as more meetings are added."]), ""]
    return "\n".join(lines)


def build_report(evidence_dir: Path | str = "evidence") -> str:
    return write_report(evidence_dir).read_text(encoding="utf-8")


def write_report(evidence_dir: Path | str = "evidence") -> Path:
    import autopopulate
    evidence_dir = Path(evidence_dir)
    loaded = autopopulate.load_captures(evidence_dir)
    captures = loaded[0] if isinstance(loaded, tuple) else loaded
    flags_path = evidence_dir / "discrepancy-flags.json"
    flags = []
    if flags_path.exists():
        data = json.loads(flags_path.read_text(encoding="utf-8"))
        flags = data if isinstance(data, list) else data.get("flags", [])
    out = evidence_dir / "report.md"
    out.write_text(render_report(captures, flags), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(write_report())
