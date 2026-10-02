import pytest

from facts import (
    add_manual_fact, extract_from_pages, fact_id, load_facts, review_fact, save_proposed,
)

SOURCE = {"type": "evidence", "ref": "rec-1", "sha256": "ab" * 32, "title": "Minutes"}


def extract(text, protection="public"):
    return extract_from_pages([text], SOURCE, protection)


def values(facts, kind):
    return sorted(f["value"] for f in facts if f["kind"] == kind)


def test_dates_in_common_formats_are_normalized_and_invalid_dates_skipped():
    facts = extract("Meeting held August 12, 2026; notice posted 8/5/2026 and filed 2026-08-01. Bogus: February 30, 2026 and 13/40/2026.")
    assert values(facts, "date") == ["2026-08-01", "2026-08-05", "2026-08-12"]


def test_amounts_support_commas_cents_and_scale_words():
    facts = extract("Paid $1,234.56 on the invoice, a $12.5 million award, $3M reserve, and $900 fee. Not money: 5 dollars.")
    assert values(facts, "amount") == sorted(["1234.56", "12500000.00", "3000000.00", "900.00"])


def test_vote_patterns_without_duplicates():
    facts = extract("The motion passed 5-2. It was approved by a 6 to 1 vote. Ayes: 4 Nays: 3. See Section 5-2 of the code.")
    assert values(facts, "vote") == ["4-3", "5-2", "6-1"]
    assert len([f for f in facts if f["kind"] == "vote" and f["value"] == "6-1"]) == 1


def test_each_fact_carries_exact_passage_source_and_starts_proposed():
    text = "Preamble. The council approved a $50,000 grant on March 3, 2025 by a vote of 5-2. Closing remarks."
    facts = extract(text, protection="restricted")
    amount = next(f for f in facts if f["kind"] == "amount")
    assert "$50,000 grant" in amount["passage"]
    assert text[amount["start"]:amount["end"]] == amount["matched_text"] == "$50,000"
    assert amount["source"]["sha256"] == SOURCE["sha256"]
    assert amount["status"] == "proposed" and amount["protection"] == "restricted"


def test_pdf_pages_are_recorded_for_multi_page_sources():
    facts = extract_from_pages(["Nothing here.", "Contract signed June 1, 2025."], SOURCE, "public")
    assert [f["page"] for f in facts] == [2]


def test_ids_are_stable_and_saving_is_idempotent(tmp_path):
    path = tmp_path / "facts.json"
    facts = extract("Paid $10 on May 5, 2025.")
    assert facts[0]["id"] == fact_id(SOURCE["sha256"], None, facts[0]["kind"], facts[0]["value"], facts[0]["start"])
    assert save_proposed(path, facts)["added"] == len(facts)
    assert save_proposed(path, facts) == {"added": 0, "already_present": len(facts), "truncated": False}
    assert len(load_facts(path)) == len(facts)


def test_review_requires_reviewer_and_rejection_note(tmp_path):
    path = tmp_path / "facts.json"
    facts = extract("Paid $10.")
    save_proposed(path, facts)
    fid = facts[0]["id"]
    with pytest.raises(ValueError):
        review_fact(path, fid, {"disposition": "confirmed", "reviewer": ""})
    with pytest.raises(ValueError):
        review_fact(path, fid, {"disposition": "rejected", "reviewer": "H"})
    reviewed = review_fact(path, fid, {"disposition": "confirmed", "reviewer": "H", "corrected_value": "100.00"})
    assert reviewed["status"] == "confirmed" and reviewed["value"] == "100.00" and reviewed["original_value"] == "10.00"
    with pytest.raises(ValueError):
        review_fact(path, fid, {"disposition": "rejected", "reviewer": "H", "note": "changed my mind"})


def test_manual_facts_need_source_passage_and_valid_date(tmp_path):
    path = tmp_path / "facts.json"
    entry = {"kind": "date", "value": "2026-02-30", "passage": "Warrant issued Feb 30", "reviewer": "H"}
    with pytest.raises(ValueError):
        add_manual_fact(path, entry, SOURCE, "restricted")
    with pytest.raises(ValueError):
        add_manual_fact(path, {**entry, "value": "2026-02-27", "passage": ""}, SOURCE, "restricted")
    fact = add_manual_fact(path, {**entry, "value": "2026-02-27"}, SOURCE, "restricted")
    assert fact["status"] == "confirmed" and fact["protection"] == "restricted" and fact["reviewer"] == "H"
