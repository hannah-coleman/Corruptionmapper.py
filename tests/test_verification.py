import json

import pytest

import lead_packet
import verification as v
from discrepancy_engine import load_flags


def flag(**extra):
    base = {"id": "f1", "kind": "vote-tally", "message": "Minutes announce a 6-2 vote.", "status": "open", "protection": "public",
            "vector": {"text_method": "ocr"}, "link": {"detail": "2026-02-23"}, "innocent_explanations": ["OCR error"], "next_action": "Check",
            "facts": [{"passage": "roll call", "source": {"ref": "http://x", "sha256": "ab"}}]}
    base.update(extra)
    return base


CHECK = {"method": "page-image", "result": "matches", "reviewer": "H", "note": "Page 3 reads 6 yes 1 no", "page": "3"}


def write(tmp_path, flags):
    (tmp_path / "discrepancy-flags.json").write_text(json.dumps(flags), encoding="utf-8")
    return tmp_path / "discrepancy-flags.json"


def test_ocr_lead_is_unverified_until_checked(tmp_path):
    path = write(tmp_path, [flag()])
    assert v.verification_level(load_flags(path)[0]) == "unverified-ocr"
    v.verify_flag(path, "f1", CHECK)
    assert v.verification_level(load_flags(path)[0]) == "verified"


def test_changed_text_invalidates_check(tmp_path):
    path = write(tmp_path, [flag()])
    v.verify_flag(path, "f1", CHECK)
    changed = load_flags(path)[0]
    changed["facts"][0]["passage"] = "different text"
    assert v.verification_level(changed) == "stale-check"


@pytest.mark.parametrize("bad", [{"method": "guess"}, {"result": "maybe"}, {"reviewer": ""}, {"note": ""}, {"result": "corrected"}])
def test_verification_requires_complete_input(tmp_path, bad):
    path = write(tmp_path, [flag()])
    with pytest.raises(ValueError):
        v.verify_flag(path, "f1", {**CHECK, **bad})


def test_packet_separates_levels_rehashes_and_withholds_non_public(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    raw = evidence / "a.bin"
    raw.write_bytes(b"hello")
    import hashlib
    digest = hashlib.sha256(b"hello").hexdigest()
    (evidence / "manifest.jsonl").write_text(json.dumps({"status": "collected", "sha256": digest, "raw_file": str(raw), "url": "http://x", "captured_at": "2026-01-01T00:00:00"}) + "\n")
    good = flag(facts=[{"passage": "roll call", "source": {"ref": "http://x", "sha256": digest}}])
    path = write(evidence, [good, flag(id="f2", protection="counsel")])
    v.verify_flag(path, "f1", CHECK)
    packet = lead_packet.build_packet(evidence)
    assert packet["withheld_non_public"] == 1 and len(packet["leads"]) == 1
    assert packet["leads"][0]["level"] == "verified" and packet["leads"][0]["sources"][0]["custody"] == "intact"
    raw.write_bytes(b"tampered")
    assert lead_packet.build_packet(evidence)["custody_problems"][0]["custody"] == "HASH MISMATCH"
    text = lead_packet.render_packet(packet)
    assert "not a finding of wrongdoing" in text and "Verified against the original record" in text
