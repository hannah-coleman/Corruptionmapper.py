import re

import pytest

import case_review as cr
from tests.test_case_review import BANNED


def add(path, **k):
    base = {"case_id": "C1", "kind": "report", "source": "FOIA 1", "text": "x", "incident_date": "2026-01-05"}
    base.update(k)
    return cr.add_entry(path, base)


def test_basis_defaults_and_validation(tmp_path):
    p = tmp_path / "c.json"
    assert add(p)["basis"] == "document"
    assert add(p, kind="statement")["basis"] == "memory"
    with pytest.raises(ValueError):
        add(p, basis="rumor")


def test_packet_has_timeline_index_questions_and_redacts(tmp_path):
    p = tmp_path / "c.json"
    add(p, title="Report on Jane Doe", text="Time of arrest: 10:42 PM.", private_people="Jane Doe", basis="document")
    add(p, kind="booking", title="Booking", text="Arrest time: 11:15 PM", basis="photo")
    add(p, kind="statement", title="Recollection", incident_date="", doc_date="", text="I saw it.")
    add(p, kind="news", title="Post", basis="social", text="a post")
    text = cr.build_packet(p, "C1")
    for heading in ("## 1. Timeline", "## 2. Evidence index", "## 3. Where the records differ", "## 5. Open questions"):
        assert heading in text
    assert "Jane Doe" not in text and "different values for arrest time" in text
    assert "rests on recollection only" in text and "has no date" in text and "saved with its address" in text
    assert "Photo or screenshot: 1" in text
    assert not BANNED.search(text)
    assert "Jane Doe" in cr.build_packet(p, "C1", redacted=False)


def test_packet_needs_entries(tmp_path):
    with pytest.raises(ValueError):
        cr.build_packet(tmp_path / "none.json", "C1")
