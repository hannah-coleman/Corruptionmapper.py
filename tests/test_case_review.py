import re

import pytest

import case_review as cr

BANNED = re.compile(r"\b(liar|lied|lying|perjur\w*|forg\w+|violat\w+|guilty|illegal|unlawful|corrupt\w*|fabricat\w+|manufactur\w+)\b", re.I)


def add(path, **k):
    base = {"case_id": "C1", "kind": "report", "source": "FOIA 1", "text": "x", "incident_date": "2026-01-05"}
    base.update(k)
    return cr.add_entry(path, base)


def test_requires_source_kind_and_text(tmp_path):
    p = tmp_path / "c.json"
    for bad in ({"source": ""}, {"kind": "bogus"}, {"text": ""}, {"case_id": ""}, {"doc_date": "May"}):
        with pytest.raises(ValueError):
            add(p, **bad)


def test_differing_times_and_charges_are_reported_neutrally(tmp_path):
    p = tmp_path / "c.json"
    add(p, title="Report", text="Time of arrest: 10:42 PM. Charge: Disorderly conduct. Location: 5th and Main.")
    add(p, kind="booking", title="Booking", text="Arrest time: 11:15 PM\nBooking time: 10:50 PM\nCharge: Public intoxication\nLocation: 5th and Main")
    a = cr.analyze(p, "C1")
    fields = {d["field"] for d in a["differences"]}
    assert {"arrest time", "charge"} <= fields and "location" not in fields
    assert any(d["kind"] == "sequence" for d in a["differences"])
    assert all(d["ordinary_explanations"] and d["next_step"] for d in a["differences"])
    assert not BANNED.search(" ".join(d["message"] + d["next_step"] for d in a["differences"]))


def test_same_values_make_no_flag(tmp_path):
    p = tmp_path / "c.json"
    add(p, text="Time of arrest: 10:42 PM")
    add(p, kind="booking", text="Arrest time: 22:42")
    assert cr.analyze(p, "C1")["differences"] == []


def test_policy_beside_record_and_version_note(tmp_path):
    p = tmp_path / "c.json"
    add(p, kind="policy", title="Use of force SOP", agency="PD", effective_date="2026-03-01",
        text="Officers shall document every use of force in a written supplemental report before the end of shift.")
    add(p, kind="statement", title="Recollection", text="He used force and no supplemental report was shown to me.")
    add(p, title="Incident report", text="Officer wrote a brief narrative. The subject was handcuffed.")
    item = cr.analyze(p, "C1")["policy"][0]
    assert "after the earliest incident" in item["version_note"]
    assert any(r["given_as"].startswith("recollection") for r in item["record_passages"])
    assert "reviewer to weigh" in item["note"]


def test_absence_note_is_cautious(tmp_path):
    p = tmp_path / "c.json"
    add(p, kind="policy", text="Supervisors must notify headquarters regarding any vehicle pursuit immediately.")
    add(p, text="Unrelated text here about weather.")
    assert "may reflect what was entered" in cr.analyze(p, "C1")["policy"][0]["note"]


def test_wording_features(tmp_path):
    p = tmp_path / "c.json"
    add(p, text="The subject was arrested. It was determined that a search was needed. The officer arrested him.")
    features = {n["feature"] for n in cr.analyze(p, "C1")["wording"]}
    assert features == {"hedged or indirect phrasing", "action described without naming who did it"}


def test_redaction_codes_private_people_but_not_officials_or_consenting(tmp_path):
    p = tmp_path / "c.json"
    add(p, text="Jane Doe was arrested; phone 870-555-1234, SSN 123-45-6789, email j@x.com. It was reported that Officer Smith wrote it.",
        private_people="Jane Doe", officials="Officer Smith")
    report = cr.build_report(p, "C1")
    assert "Jane Doe" not in report and "Person-A" in report and "Officer Smith" in report
    assert not re.search(r"870-555|123-45|j@x", report)
    cr.set_consent(p, "jane doe", True)
    assert "Jane Doe" in cr.build_report(p, "C1")
    assert "Jane Doe" in cr.build_report(p, "C1", redacted=False)


def test_patterns_need_two_cases_and_carry_caution(tmp_path):
    p = tmp_path / "c.json"
    add(p, case_id="A", officials="Officer Smith", text="Time of arrest: 10:00 PM")
    add(p, case_id="A", kind="booking", officials="Officer Smith", text="Arrest time: 11:00 PM")
    add(p, case_id="B", officials="Officer Smith; Officer Jones", text="nothing")
    result = cr.patterns(p)
    rows = {r["name"]: r for r in result["officials_in_two_or_more_cases"]}
    assert rows["Officer Smith"]["cases"] == 2 and rows["Officer Smith"]["cases_with_record_differences"] == 1
    assert "Officer Jones" not in rows and "not rates" in result["caution"]
    assert not BANNED.search(result["caution"])


def test_report_wording_is_neutral(tmp_path):
    p = tmp_path / "c.json"
    add(p, text="Time of arrest: 10:42 PM")
    add(p, kind="booking", text="Arrest time: 11:15 PM")
    assert not BANNED.search(cr.build_report(p, "C1"))


def test_policy_request_is_a_neutral_unsent_draft():
    import lead_actions
    draft = lead_actions.policy_request("Some Police Department")
    assert not BANNED.search(draft["request_text"]) and "use of force" in draft["description"]
    with pytest.raises(ValueError):
        lead_actions.policy_request(" ")


def test_mark_sent_tracks_deadline_and_only_applies_to_drafts(tmp_path):
    import request_queue as rq
    path = tmp_path / "r.json"
    record = rq.add_request(path, {"agency": "A", "description": "d"})
    for bad in (("", ""), ("May", ""), ("2026-11-05", "soon")):
        with pytest.raises(ValueError):
            rq.mark_sent(path, record["id"], *bad)
    sent = rq.mark_sent(path, record["id"], "2026-11-05", "2026-11-10")
    assert sent["status"] == "submitted"
    assert rq.deadline_status(rq.list_requests(path), "2026-11-06")[0]["days_remaining"] == 4
    with pytest.raises(ValueError):
        rq.mark_sent(path, record["id"], "2026-11-05")
    with pytest.raises(ValueError):
        rq.mark_sent(path, "missing", "2026-11-05")
