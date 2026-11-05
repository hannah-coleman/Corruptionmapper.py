import pytest

from reference_register import load_references, save_reference


def test_saves_citation_without_article_text(tmp_path):
    path = tmp_path / "refs.json"
    save_reference(path, {"url": "https://example.org/a", "summary": "Reported budget overrun.", "records_to_check": ["city budget"]})
    assert load_references(path)[0]["status"] == "reported-not-verified"


@pytest.mark.parametrize("entry", [
    {"url": "ftp://x.org", "summary": "s"},
    {"url": "http://abcdefghij.onion/", "summary": "s"},
    {"url": "https://example.org", "summary": ""},
    {"url": "https://example.org", "summary": "x" * 401},
])
def test_rejects_bad_references(tmp_path, entry):
    with pytest.raises(ValueError):
        save_reference(tmp_path / "r.json", entry)
