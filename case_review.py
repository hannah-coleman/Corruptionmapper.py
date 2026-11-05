"""Neutral case review: line up the records someone enters and show where they differ.

Principles built into the code:
- Every entry cites its source. A recollection is stored as "given", never treated as established.
- Output states what each record says and where records differ. It never says who is right, never
  names intent, and never applies a law to anyone's facts. Policies are shown beside records for a
  reviewer (or an attorney) to weigh.
- Private individuals (arrestees, victims, witnesses, minors) are replaced by codes in exports unless
  they have agreed to be named. People acting in an official role keep their names, because a
  pattern question cannot be asked without them. Only official acts belong in those fields.
- Pattern counts come from entries people chose to enter, so they are not rates.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from uuid import uuid4

KINDS = {"policy": "Policy or SOP", "report": "Official report", "booking": "Booking or jail record", "statement": "Recollection or statement",
         "news": "News or public statement", "other": "Other record"}
MAX_TEXT = 400_000
MAX_ENTRIES = 5000

DIFFERENCE_EXPLANATIONS = ["A clerical entry or transcription error.", "Different clocks or time sources.",
                           "The records may describe different moments or different events.", "One record may be a draft or a later revision."]
LIMITS = ["Entries come from people who chose to enter them, so counts are not rates and say nothing about how common anything is.",
          "A difference between records is a reason to ask for the originals. It does not show which record is accurate or why they differ.",
          "A recollection is shown as the person gave it; it is not treated as established.",
          "Absence of a topic in the entered records does not show it did not happen."]


def _load(path: Path) -> dict:
    if not Path(path).exists():
        return {"entries": [], "people": []}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _day(value: str, label: str, required: bool = False) -> str:
    value = str(value or "").strip()
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(f"{label} must be a date like 2026-03-31.") from error


def _names(value) -> list[str]:
    items = value if isinstance(value, list) else re.split(r"[;\n]", str(value or ""))
    seen, out = set(), []
    for item in items:
        name = " ".join(str(item).split())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def _code(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return f"Person-{letters}"


def add_entry(path: Path | str, payload: dict) -> dict:
    data = _load(path)
    if len(data["entries"]) >= MAX_ENTRIES:
        raise ValueError("Entry limit reached.")
    kind = str(payload.get("kind", "")).strip()
    if kind not in KINDS:
        raise ValueError("Choose what kind of record this is.")
    case_id = " ".join(str(payload.get("case_id", "")).split())
    text = str(payload.get("text", "")).strip()
    source = " ".join(str(payload.get("source", "")).split())
    if not case_id:
        raise ValueError("A case name is required.")
    if not source:
        raise ValueError("Every entry must cite its source (where the record came from).")
    if not text:
        raise ValueError("Paste or type the record's text.")
    if len(text) > MAX_TEXT:
        raise ValueError("That text is too long. Split it into separate entries.")
    entry = {"id": uuid4().hex[:12], "case_id": case_id, "kind": kind, "title": " ".join(str(payload.get("title", "")).split()) or KINDS[kind],
             "doc_date": _day(payload.get("doc_date"), "Document date"), "incident_date": _day(payload.get("incident_date"), "Incident date"),
             "effective_date": _day(payload.get("effective_date"), "Policy effective date"), "agency": " ".join(str(payload.get("agency", "")).split()),
             "source": source, "text": text, "officials": _names(payload.get("officials")), "private_people": _names(payload.get("private_people"))}
    known = {p["name"].lower() for p in data["people"]}
    for name in entry["private_people"]:
        if name.lower() not in known:
            data["people"].append({"name": name, "code": _code(len(data["people"])), "named_ok": False})
            known.add(name.lower())
    data["entries"].append(entry)
    _save(path, data)
    return entry


def set_consent(path: Path | str, name: str, allowed: bool) -> dict:
    data = _load(path)
    person = next((p for p in data["people"] if p["name"].lower() == str(name).strip().lower()), None)
    if person is None:
        raise ValueError("No such person is listed.")
    person["named_ok"] = bool(allowed)
    _save(path, data)
    return person


def cases(path: Path | str) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)
    for entry in _load(path)["entries"]:
        counts[entry["case_id"]] += 1
    return [{"case_id": name, "entries": count} for name, count in sorted(counts.items())]


_PII = [(re.compile(r"(?i)\b(?:driver'?s? licen[sc]e|dl|ssn)\s*(?:no\.?|number|#)?\W{0,3}[\w-]{5,}"), "[ID number removed]"),
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN removed]"),
        (re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"), "[phone removed]"),
        (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email removed]"),
        (re.compile(r"(?i)\b(?:dob|date of birth|d\.o\.b\.)\W{0,3}[\w/ ,.-]{4,20}"), "[date of birth removed]")]


def redact(text: str, people: list[dict]) -> str:
    """Replace private individuals who have not agreed to be named, and common identifiers, with codes."""
    for person in people:
        if person.get("named_ok"):
            continue
        parts = person["name"].split()
        variants = {person["name"]}
        if len(parts) > 1:
            variants.add(f"{parts[-1]}, {' '.join(parts[:-1])}")
            if len(parts[-1]) >= 4:
                variants.add(parts[-1])
        for variant in sorted(variants, key=len, reverse=True):
            text = re.sub(rf"(?<![\w]){re.escape(variant)}(?![\w])", person["code"], text, flags=re.IGNORECASE)
    for pattern, label in _PII:
        text = pattern.sub(label, text)
    return text


def _minutes(value: str) -> int | None:
    match = re.match(r"(\d{1,2}):(\d{2})\s*([ap])?\.?m?\.?", value.strip().lower())
    if not match:
        return None
    hour, minute, ampm = int(match.group(1)), int(match.group(2)), match.group(3)
    if ampm == "p" and hour < 12:
        hour += 12
    if ampm == "a" and hour == 12:
        hour = 0
    return hour * 60 + minute if hour < 24 and minute < 60 else None


TIME = r"(\d{1,2}:\d{2}\s*(?:[ap]\.?m\.?)?)"
FIELDS = {
    "arrest time": (re.compile(rf"(?:time of arrest|arrest(?:ed)?\s+(?:at|time)|arrest time)\W{{0,3}}{TIME}", re.I), "time"),
    "booking time": (re.compile(rf"(?:booking time|booked\s+(?:at|time)|time booked)\W{{0,3}}{TIME}", re.I), "time"),
    "release time": (re.compile(rf"(?:release time|released\s+at|time released)\W{{0,3}}{TIME}", re.I), "time"),
    "statute cited": (re.compile(r"(?:A\.?C\.?A\.?\s*)?§\s*(\d+-\d+-\d+(?:\([a-z0-9]+\))*)", re.I), "text"),
    "charge": (re.compile(r"\bcharges?\s*:\s*([^\n;.]{3,80})", re.I), "text"),
    "location": (re.compile(r"\blocation(?: of (?:arrest|incident|stop))?\s*:\s*([^\n;.]{3,80})", re.I), "text"),
    "number of people present": (re.compile(r"\b(?:officers|deputies|persons|people) (?:present|on scene)\s*:\s*(\d+)", re.I), "text"),
}


def _field_values(entry: dict) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for label, (pattern, kind) in FIELDS.items():
        for match in pattern.finditer(entry["text"]):
            raw = " ".join(match.group(1).split())
            norm = str(_minutes(raw)) if kind == "time" else raw.lower().rstrip(" .")
            if norm != "None":
                out.setdefault(label, []).append((norm, raw))
    return out


def _entry_ref(entry: dict) -> dict:
    return {"id": entry["id"], "title": entry["title"], "kind": KINDS[entry["kind"]], "source": entry["source"]}


def record_differences(entries: list[dict]) -> list[dict]:
    """Labelled values that differ between the entered non-policy records for one case."""
    findings = []
    records = [e for e in entries if e["kind"] != "policy"]
    by_label: dict[str, list[tuple[dict, str, str]]] = defaultdict(list)
    for entry in records:
        for label, values in _field_values(entry).items():
            for norm, raw in values:
                by_label[label].append((entry, norm, raw))
    for label, rows in sorted(by_label.items()):
        docs = {r[0]["id"] for r in rows}
        if len(docs) < 2 or len({r[1] for r in rows}) < 2:
            continue
        findings.append({"kind": "values-differ", "field": label,
                         "message": f"The records entered for this case give different values for {label}.",
                         "values": [{**_entry_ref(e), "value": raw} for e, _norm, raw in rows],
                         "ordinary_explanations": DIFFERENCE_EXPLANATIONS,
                         "next_step": "Request the original or system log for each (for example the dispatch or jail booking system) and compare."})
    times = {}
    for entry in records:
        for label in ("arrest time", "booking time", "release time"):
            vals = _field_values(entry).get(label)
            if vals:
                times.setdefault(label, []).append((entry, int(vals[0][0]), vals[0][1]))
    for earlier, later in (("arrest time", "booking time"), ("booking time", "release time")):
        for a_entry, a_min, a_raw in times.get(earlier, []):
            for b_entry, b_min, b_raw in times.get(later, []):
                if a_entry["incident_date"] and b_entry["incident_date"] and a_entry["incident_date"] != b_entry["incident_date"]:
                    continue
                if b_min < a_min:
                    findings.append({"kind": "sequence", "field": f"{earlier} / {later}",
                                     "message": f"A {later} ({b_raw}) is recorded as earlier in the day than a {earlier} ({a_raw}).",
                                     "values": [{**_entry_ref(a_entry), "value": a_raw}, {**_entry_ref(b_entry), "value": b_raw}],
                                     "ordinary_explanations": ["The events may fall on different calendar days.", *DIFFERENCE_EXPLANATIONS[:2]],
                                     "next_step": "Check the dates attached to each time in the original records."})
    return findings


HEDGES = ["it was determined", "it was found", "it was observed", "it was noted", "it was reported", "it is believed", "it appeared",
          "appeared to", "appears to", "allegedly", "reportedly", "believed to", "was said to", "claimed to", "stated that"]
PASSIVE = re.compile(r"\b(?:was|were)\s+(arrested|stopped|detained|searched|handcuffed|struck|seized|charged|booked|released|removed|placed|taken|"
                     r"transported|restrained|questioned|informed|advised|notified|cited)\b(?!\s+by\b)", re.I)


def wording_notes(entry: dict) -> list[dict]:
    """Wording features only. They describe how a sentence is built, not what happened or why."""
    notes = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", entry["text"]):
        lower = sentence.lower()
        found = [h for h in HEDGES if h in lower]
        if found:
            notes.append({"entry": entry["id"], "feature": "hedged or indirect phrasing", "phrase": found[0], "sentence": sentence.strip()[:300]})
        match = PASSIVE.search(sentence)
        if match:
            notes.append({"entry": entry["id"], "feature": "action described without naming who did it", "phrase": match.group(0), "sentence": sentence.strip()[:300]})
    return notes[:60]


STOP = set("shall must will that this with from have been being they them their there which would could should about after before under over into upon when where while other such than then also only each".split())
OBLIGATION = re.compile(r"\b(shall not|must not|shall|must|required to|may not|is responsible for|will be)\b", re.I)


def _keywords(sentence: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{5,}", sentence.lower()) if w not in STOP}


def policy_comparison(entries: list[dict]) -> list[dict]:
    """Show each policy requirement beside passages in the case records that use the same terms."""
    policies = [e for e in entries if e["kind"] == "policy"]
    records = [e for e in entries if e["kind"] != "policy"]
    incident_dates = sorted({e["incident_date"] for e in records if e["incident_date"]})
    out = []
    for policy in policies:
        version_note = ""
        if policy["effective_date"] and incident_dates and policy["effective_date"] > incident_dates[0]:
            version_note = (f"This policy's effective date ({policy['effective_date']}) is after the earliest incident date entered "
                            f"({incident_dates[0]}). Confirm which version was in force.")
        elif not policy["effective_date"]:
            version_note = "No effective date was entered for this policy, so the version in force on the incident date is unconfirmed."
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", policy["text"]):
            sentence = sentence.strip()
            if not (OBLIGATION.search(sentence) and len(sentence) > 25):
                continue
            keys = _keywords(sentence)
            if len(keys) < 2:
                continue
            related = []
            for record in records:
                for passage in re.split(r"(?<=[.!?])\s+|\n+", record["text"]):
                    shared = keys & _keywords(passage)
                    if len(shared) >= max(2, len(keys) // 3):
                        related.append({**_entry_ref(record), "passage": passage.strip()[:400], "shared_terms": sorted(shared),
                                        "given_as": "recollection as given, not established" if record["kind"] == "statement" else "record text"})
            out.append({"policy": _entry_ref(policy), "agency": policy["agency"], "effective_date": policy["effective_date"], "version_note": version_note,
                        "requirement": sentence[:500], "record_passages": related[:6],
                        "note": ("No passage in the entered records uses these terms. That may reflect what was entered, not what happened."
                                 if not related else "The passages below use similar terms. Whether they are consistent with the requirement is for the reviewer to weigh.")})
    return out[:200]


def timeline(entries: list[dict]) -> list[dict]:
    rows = [{"date": e["incident_date"] or e["doc_date"] or "undated", "kind": KINDS[e["kind"]], "title": e["title"], "source": e["source"], "id": e["id"]}
            for e in entries if e["kind"] != "policy"]
    return sorted(rows, key=lambda r: (r["date"] == "undated", r["date"]))


def analyze(path: Path | str, case_id: str) -> dict:
    data = _load(path)
    entries = [e for e in data["entries"] if e["case_id"] == case_id]
    if not entries:
        raise ValueError("No entries for that case.")
    wording = [n for e in entries if e["kind"] != "policy" for n in wording_notes(e)]
    return {"case_id": case_id, "entries": [{k: e[k] for k in ("id", "kind", "title", "doc_date", "incident_date", "agency", "source")} for e in entries],
            "timeline": timeline(entries), "differences": record_differences(entries), "policy": policy_comparison(entries),
            "wording": wording, "limits": LIMITS}


def patterns(path: Path | str) -> dict:
    """How often each named official appears across entered cases. Counts of entries, not rates."""
    data = _load(path)
    by_case: dict[str, list[dict]] = defaultdict(list)
    for entry in data["entries"]:
        by_case[entry["case_id"]].append(entry)
    with_differences = {case for case, items in by_case.items() if record_differences(items)}
    seen: dict[str, dict] = {}
    for case, items in by_case.items():
        for entry in items:
            for name in entry["officials"]:
                row = seen.setdefault(name.lower(), {"name": name, "cases": set(), "agencies": set()})
                row["cases"].add(case)
                if entry["agency"]:
                    row["agencies"].add(entry["agency"])
    rows = [{"name": r["name"], "cases": len(r["cases"]), "cases_with_record_differences": len(r["cases"] & with_differences),
             "agencies": sorted(r["agencies"])} for r in seen.values() if len(r["cases"]) >= 2]
    return {"cases_entered": len(by_case), "cases_with_record_differences": len(with_differences),
            "officials_in_two_or_more_cases": sorted(rows, key=lambda r: r["name"].lower()),
            "caution": "Listed alphabetically. Appearing in a case, or in a case where records differ, says nothing about conduct; many cases involve the same few officials by role. "
                       "Entries are self-selected, so these are counts and not rates.", "limits": LIMITS}


def build_report(path: Path | str, case_id: str, redacted: bool = True) -> str:
    data = _load(path)
    analysis = analyze(path, case_id)
    people = data["people"] if redacted else []
    clean = (lambda s: redact(str(s), people)) if redacted else str
    lines = [f"# Record comparison: {clean(case_id)}", "",
             "This document lines up records that were entered and shows where they differ. It does not say which record is accurate, "
             "does not state why any difference exists, and is not legal advice. Each item cites the record it came from.", "",
             "## Limits", *[f"- {item}" for item in analysis["limits"]], "",
             f"Private individuals are {'replaced by codes unless they agreed to be named' if redacted else 'shown by name (unredacted)'}. People acting in an official role are named."
             if redacted else "WARNING: unredacted copy. Do not share.", "", "## Timeline"]
    lines += [f"- {row['date']}: {clean(row['title'])} ({row['kind']}; source: {clean(row['source'])})" for row in analysis["timeline"]] or ["- None."]
    lines += ["", "## Where the records differ"]
    for item in analysis["differences"]:
        lines += [f"### {item['message']}", *[f"- {clean(v['title'])} ({v['kind']}): {clean(v['value'])}  [source: {clean(v['source'])}]" for v in item["values"]],
                  f"- Ordinary explanations: {' '.join(item['ordinary_explanations'])}", f"- Next step: {item['next_step']}", ""]
    if not analysis["differences"]:
        lines += ["None found in the labelled fields (times, charge, statute, location, people present). This check reads only those labelled fields.", ""]
    lines += ["## Policy text beside record text"]
    for item in analysis["policy"]:
        lines += [f"### {clean(item['policy']['title'])} ({clean(item['agency']) or 'agency not entered'})", f"Requirement as written: \"{clean(item['requirement'])}\""]
        if item["version_note"]:
            lines.append(f"Version: {item['version_note']}")
        lines += [f"- {clean(p['title'])} ({p['given_as']}): \"{clean(p['passage'])}\"  [source: {clean(p['source'])}]" for p in item["record_passages"]]
        lines += [item["note"], ""]
    if not analysis["policy"]:
        lines += ["No policy entries with requirement language were entered for this case.", ""]
    lines += ["## Wording features", "These describe how sentences are built (indirect phrasing, or an action without a named actor). They do not describe what happened or why."]
    lines += [f"- {n['feature']}: \"{clean(n['sentence'])}\"" for n in analysis["wording"][:40]] or ["- None noted."]
    return "\n".join(lines) + "\n"
