import pytest

import public_statements as ps


def test_unsupported_amount_is_flagged_and_supported_is_not(tmp_path):
    path = tmp_path / "s.json"
    item = ps.save_statement(path, {"url": "https://example.org/p", "author": "Official", "quote": "We saved $2 million and spent $47,739.23."})
    flags = ps.compare([item], [{"kind": "amount", "value": "47739.23"}])
    assert len(flags) == 1 and "2,000,000" in flags[0]["message"]
    assert flags[0]["innocent_explanations"] and flags[0]["facts"][0]["passage"]


@pytest.mark.parametrize("entry", [{"url": "http://a.onion", "author": "x", "quote": "q"}, {"url": "https://e.org", "author": "", "quote": "q"}, {"url": "https://e.org", "author": "x", "quote": ""}])
def test_rejects_bad_statements(tmp_path, entry):
    with pytest.raises(ValueError):
        ps.save_statement(tmp_path / "s.json", entry)
