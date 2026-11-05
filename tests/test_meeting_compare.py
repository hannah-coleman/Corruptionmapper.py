import hashlib

import meeting_compare as mc


def _capture(tmp_path, kind, text, meeting="_03092026-179"):
    path = tmp_path / f"{kind}-{meeting}.html"
    data = f"<html><body>{text}</body></html>".encode()
    path.write_bytes(data)
    return {"url": f"https://city.example/AgendaCenter/ViewFile/{kind}/{meeting}", "path": path, "content_type": "text/html",
            "sha256": hashlib.sha256(data).hexdigest()}


MINUTES = ("Those present were Ann Adams, Bob Baker, Cy Cole. "
           "Motion that the resolution be adopted. Roll Call: Adams, yes; Baker, yes; Cole, yes. Motion passed two to one. Resolution adopted. (Resolution No. 2026-02) "
           "Roll Call: Adams, yes; Baker, yes; Cole, no. Motion passed three to zero. Resolution adopted. (Resolution No. 2026-04)")


def test_vote_tally_mismatch_is_flagged_with_passage_and_source(tmp_path):
    flags = mc.meeting_flags([_capture(tmp_path, "Minutes", MINUTES)])
    tally = [f for f in flags if f["kind"] == "vote-tally"]
    assert len(tally) == 2
    assert "Roll Call" in tally[0]["facts"][0]["passage"] and tally[0]["facts"][0]["source"]["ref"].startswith("https://city.example")
    assert tally[0]["innocent_explanations"] and tally[0]["status"] == "open"


def test_garbled_roll_call_is_not_guessed_at(tmp_path):
    text = "Roll Call: Adams, yes; Baker,- yes; Cole yes. Motion passed three to zero."
    assert not [f for f in mc.meeting_flags([_capture(tmp_path, "Minutes", text)]) if f["kind"] == "vote-tally"]


def test_instrument_numbering_gap_and_agenda_only_property(tmp_path):
    agenda = "x " * 400 + "The property is located at 304 Tech Street and is owned by A Person."
    flags = mc.meeting_flags([_capture(tmp_path, "Minutes", MINUTES), _capture(tmp_path, "Agenda", agenda)])
    gap = [f for f in flags if f["kind"] == "instrument-gap"]
    assert gap and "2026-3" in gap[0]["message"]
    assert any(f["kind"] == "agenda-only" and "304 Tech Street" in f["message"] for f in flags)


def test_flag_ids_are_stable_so_reviews_survive_reruns(tmp_path):
    captures = [_capture(tmp_path, "Minutes", MINUTES)]
    assert [f["id"] for f in mc.meeting_flags(captures)] == [f["id"] for f in mc.meeting_flags(captures)]
