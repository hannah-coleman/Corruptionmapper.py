"""Cross-check City Council agendas and minutes (and the minutes against themselves).

Every finding is a *lead*, not a conclusion: each flag quotes the exact passages, names the source
documents, and lists innocent explanations. Text may come from OCR of scanned pages, which can
misread characters, so flags from OCR text are marked and must be checked against the page image.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from collections import defaultdict
from pathlib import Path

from fact_sources import pages_for_file
from ocr import CACHE as OCR_CACHE

_URL = re.compile(r"AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{2})(\d{2})(\d{4})-(\d+)", re.IGNORECASE)
_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
_NAME = r"[A-Z][A-Za-z'’\-]+"
_ROLL = re.compile(rf"Roll\s*Call\s*:?\s*((?:\s*{_NAME},\s*(?:yes|no|nay|abstain\w*|absent|present)\s*[;.,]?)+)", re.IGNORECASE)
_VOTER = re.compile(rf"({_NAME}),\s*(yes|no|nay|abstain\w*|absent|present)", re.IGNORECASE)
_TALLY = re.compile(r"\b(?:passed|failed|carried|adopted|approved)\s+(\w+)\s+to\s+(\w+)\b", re.IGNORECASE)
_PRESENT = re.compile(r"Those\s+present\s+were\s+(.{20,600}?)\.\s", re.IGNORECASE)
_INSTRUMENT = re.compile(r"\(\s*(Resolution|Ordinance)\s+No\.?\s*(\d{4})-(\d{1,3})\s*\)", re.IGNORECASE)
_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d{4,}(?:\.\d{2})?)")
_ADDRESS = re.compile(
    r"\b(\d{2,5})\s+((?:[NSEW]\.?\s+)?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Circle|Cir)\b\.?")
_SUFFIX = {"st": "street", "rd": "road", "ave": "avenue", "dr": "drive", "ln": "lane", "blvd": "boulevard", "ct": "court", "cir": "circle"}

EXPLAIN = {
    "vote-tally": ["OCR may have misread a name or a vote.", "The tally may refer to a different motion than the nearest roll call.", "A member may have abstained or recused, and the minutes may count that differently."],
    "not-recorded-present": ["The 'present' sentence may be incomplete, or the member may have arrived late.", "OCR may have misread a name."],
    "instrument-duplicate": ["One number may be a typographical error in the minutes.", "An item may have been re-adopted or corrected under the same number."],
    "instrument-gap": ["The missing numbers may belong to meetings whose minutes were not collected.", "Numbers may be assigned when drafted and never used."],
    "agenda-only": ["The item may have been tabled, withdrawn, or moved to another meeting.", "The minutes may describe it without repeating the address or amount, or OCR may have misread it."],
    "minutes-only": ["The item may have been added at the meeting or covered by 'other purposes' wording.", "OCR may have misread a number."],
    "no-minutes": ["Minutes are normally approved at the following meeting and may not be posted yet.", "They may be posted somewhere the collector does not reach."],
}


def _number(word: str) -> int | None:
    word = word.lower()
    return int(word) if word.isdigit() else _WORDS.get(word)


def _normalize_address(match: re.Match) -> str:
    street = match.group(3).lower().rstrip(".")
    return f"{match.group(1)} {match.group(2).lower().replace('.', '')} {_SUFFIX.get(street, street)}"


def _passage(text: str, start: int, end: int, pad: int = 160) -> str:
    return text[max(0, start - pad):end + pad].strip()


def _flag(kind: str, meeting: str, key: str, message: str, docs: list[tuple[dict, str]], tier: int, ocr: bool, next_action: str) -> dict:
    flag_id = hashlib.sha256(f"meeting|{kind}|{meeting}|{key}".encode()).hexdigest()[:16]
    return {
        "id": flag_id, "type": f"meeting-{kind}", "kind": kind, "message": message,
        "link": {"basis": "same-meeting", "detail": meeting},
        "vector": {"link_strength": "same-meeting", "fact_review": "unreviewed",
                   "source_independence": "same-meeting-documents", "text_method": "ocr" if ocr else "text-layer"},
        "tier": tier, "difference": {"summary": message, "delta": ""},
        "facts": [{"id": f"{flag_id}-{i}", "kind": "passage", "value": "", "passage": passage, "status": "proposed", "protection": "public",
                   "source": {"type": "capture", "ref": capture["url"], "sha256": capture["sha256"], "title": capture.get("title", "")}}
                  for i, (capture, passage) in enumerate(docs)],
        "innocent_explanations": EXPLAIN.get(kind, []) + (["This text came from OCR; check the page image before relying on it."] if ocr else []),
        "protection": "public", "status": "open", "next_action": next_action,
    }


_BODIES = ("City Council", "Planning and Zoning", "Board of Adjustment", "Parks", "Civil Service", "Planning Commission", "Board of Zoning")


def _body(text: str) -> str:
    head = text[:600].lower()
    found = [(head.find(name.lower()), name) for name in _BODIES if name.lower() in head]
    return min(found)[1] if found else "unknown"


def _load(captures: list[dict]) -> dict[str, dict]:
    meetings: dict[str, dict] = defaultdict(dict)
    for capture in captures:
        match = _URL.search(capture["url"])
        if not match or "packet=true" in capture["url"]:
            continue
        kind, month, day, year, ident = match.groups()
        try:
            text = " ".join(pages_for_file(capture["path"], capture.get("content_type", "")))
        except Exception:
            continue
        meetings[f"{year}-{month}-{day} (#{ident})"][kind.lower()] = {
            **capture, "text": text, "ocr": (OCR_CACHE / f"{capture['sha256']}.json").exists()}
    return meetings


def _vote_checks(meeting: str, doc: dict) -> list[dict]:
    flags, text = [], doc["text"]
    rolls = [(m.start(), m.end(), _VOTER.findall(m.group(1))) for m in _ROLL.finditer(text)]
    for tally in _TALLY.finditer(text):
        before = [r for r in rolls if r[1] <= tally.start() and tally.start() - r[1] < 400]
        yes, no = _number(tally.group(1)), _number(tally.group(2))
        if not before or yes is None or no is None:
            continue
        votes = before[-1][2]
        if len(votes) < yes + no:
            continue  # garbled roll call (usually OCR): cannot verify, so do not guess
        counted_yes = sum(v[1].lower() == "yes" for v in votes)
        counted_no = sum(v[1].lower() in {"no", "nay"} for v in votes)
        if (counted_yes, counted_no) != (yes, no):
            flags.append(_flag(
                "vote-tally", meeting, f"{tally.start()}",
                f"Minutes announce a {yes}-{no} vote but the preceding roll call records {counted_yes} yes and {counted_no} no.",
                [(doc, _passage(text, before[-1][0], tally.end()))], 3 if doc["ocr"] else 2, doc["ocr"],
                "Compare the roll call with the announced tally on the page image; if they still differ, ask the City Clerk for the signed minutes and any recording."))
    present = _PRESENT.search(text)
    if present:
        present_text = present.group(1).lower()
        voters = {name for _, _, votes in rolls for name, _ in votes}
        tokens = re.findall(r"[a-z'’\-]+", present_text)
        missing = sorted(name for name in voters
                         if not difflib.get_close_matches(name.lower(), tokens, n=1, cutoff=0.8))
        if missing:
            flags.append(_flag(
                "not-recorded-present", meeting, ",".join(missing),
                f"Roll call lists {', '.join(missing)}, who is not in the 'those present' sentence.",
                [(doc, _passage(text, present.start(), present.end()))], 3, doc["ocr"],
                "Check the attendance sentence against the roll call on the page image."))
    return flags


def _agenda_minutes_checks(meeting: str, agenda: dict, minutes: dict) -> list[dict]:
    flags, ocr = [], agenda["ocr"] or minutes["ocr"]
    a_text, m_text = agenda["text"], minutes["text"]
    m_addresses = {_normalize_address(m) for m in _ADDRESS.finditer(m_text)}
    seen: set[str] = set()
    for match in _ADDRESS.finditer(a_text):
        address = _normalize_address(match)
        if match.start() < 600 or address in m_addresses or address in seen:  # first 600 chars are letterhead
            continue
        seen.add(address)
        flags.append(_flag("agenda-only", meeting, address, f"The agenda lists a property at {match.group(0).strip()} that the minutes never mention.",
                           [(agenda, _passage(a_text, match.start(), match.end()))], 3, ocr,
                           "Check whether the item was tabled or moved; if not, ask the City Clerk what action was taken."))
    # Agendas rarely state amounts, so only amounts the agenda itself states are worth checking against the minutes.
    for source, other, label, kind in ((agenda, minutes, "agenda", "agenda-only"),):
        other_amounts = {m.group(1).replace(",", "") for m in _AMOUNT.finditer(other["text"])}
        reported: set[str] = set()
        for match in _AMOUNT.finditer(source["text"]):
            value = match.group(1).replace(",", "")
            if value in other_amounts or value in reported or float(value) < 1000:
                continue
            reported.add(value)
            other_label = "minutes" if label == "agenda" else "agenda"
            flags.append(_flag(kind, meeting, f"${value}", f"The {label} states ${match.group(1)} but that amount does not appear in the {other_label} for the same meeting.",
                               [(source, _passage(source["text"], match.start(), match.end()))], 3, ocr,
                               "Read the item in both documents; if the amount really differs or is absent, request the controlling record (approved bid, invoice, or budget amendment)."))
    return flags


def _numbering_checks(meetings: dict[str, dict]) -> list[dict]:
    flags: list[dict] = []
    seen: dict[tuple[str, int, int], list[tuple[str, dict, re.Match]]] = defaultdict(list)
    for meeting, docs in meetings.items():
        minutes = docs.get("minutes")
        if not minutes:
            continue
        for match in _INSTRUMENT.finditer(minutes["text"]):
            seen[(match.group(1).lower(), int(match.group(2)), int(match.group(3)))].append((meeting, minutes, match))
    for (kind, year, number), hits in seen.items():
        if len({meeting for meeting, _, _ in hits}) > 1:
            flags.append(_flag("instrument-duplicate", f"{kind}-{year}", str(number),
                               f"{kind.title()} No. {year}-{number} is recorded in minutes of more than one meeting ({', '.join(sorted({m for m, _, _ in hits}))}).",
                               [(doc, _passage(doc["text"], m.start(), m.end())) for _, doc, m in hits[:2]], 3, any(d["ocr"] for _, d, _ in hits),
                               "Ask the City Clerk for the adopted instrument to confirm which meeting it belongs to."))
    by_series: dict[tuple[str, int], set[int]] = defaultdict(set)
    for kind, year, number in seen:
        by_series[(kind, year)].add(number)
    for (kind, year), numbers in by_series.items():
        missing = [n for n in range(min(numbers), max(numbers) + 1) if n not in numbers]
        if missing:
            sample = next(iter(seen[(kind, year, min(numbers))]))
            flags.append(_flag("instrument-gap", f"{kind}-{year}", ",".join(map(str, missing)),
                               f"{len(missing)} {kind} number(s) between {year}-{min(numbers)} and {year}-{max(numbers)} appear in no collected minutes: {', '.join(f'{year}-{n}' for n in missing[:12])}{'…' if len(missing) > 12 else ''}.",
                               [(sample[1], _passage(sample[1]["text"], sample[2].start(), sample[2].end()))], 3, sample[1]["ocr"],
                               "Request the City Clerk's ordinance/resolution register for the year to account for these numbers."))
    return flags


def meeting_flags(captures: list[dict]) -> list[dict]:
    meetings = _load(captures)
    flags: list[dict] = []
    for meeting, docs in sorted(meetings.items()):
        if "minutes" in docs:
            flags += _vote_checks(meeting, docs["minutes"])
        if "agenda" in docs and "minutes" in docs:
            flags += _agenda_minutes_checks(meeting, docs["agenda"], docs["minutes"])
    flags += _numbering_checks(meetings)
    latest_minutes: dict[str, str] = {}
    for meeting, docs in meetings.items():
        if "minutes" in docs:
            body = _body(docs["minutes"]["text"])
            latest_minutes[body] = max(latest_minutes.get(body, ""), meeting[:10])
    for meeting, docs in sorted(meetings.items()):
        later = latest_minutes.get(_body(docs["agenda"]["text"])) if "agenda" in docs else None
        if "agenda" in docs and "minutes" not in docs and later and meeting[:10] < later:
            agenda = docs["agenda"]
            flags.append(_flag("no-minutes", meeting, "missing", f"An agenda was collected for the meeting on {meeting[:10]} but no minutes, although later minutes exist for the same body.",
                               [(agenda, agenda["text"][:300])], 3, agenda["ocr"],
                               "Check the Agenda Center for the minutes; if they are not posted, request them from the City Clerk."))
    return flags
