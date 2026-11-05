import json

import pytest

import open_data


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self, _limit=None):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_open(request, timeout=30):
    url = request.full_url
    if "usaspending" in url:
        return FakeResponse(json.dumps({"results": [{"Award ID": "X1", "Recipient Name": "ACME LLC", "Award Amount": 1500.5,
                                                       "Awarding Agency": "DoD", "Start Date": "2025-02-03", "Description": "REPAIR"}],
                                        "page_metadata": {"hasNext": False}}).encode())
    if url.endswith("search.json?q=Paragould&state%5Bid%5D=AR"):
        return FakeResponse(json.dumps({"organizations": [{"ein": 123, "name": "Test Org", "city": "Paragould", "state": "AR"}]}).encode())
    if "/organizations/" in url:
        return FakeResponse(json.dumps({"organization": {"name": "Test Org", "ein": 123},
                                        "filings_with_data": [{"tax_prd_yr": 2023, "totrevenue": 100000}]}).encode())
    raise AssertionError(f"unexpected URL {url}")


def test_collect_all_preserves_responses_with_provenance_and_skips_duplicates(tmp_path, monkeypatch):
    monkeypatch.delenv("FEC_API_KEY", raising=False)
    monkeypatch.setattr(open_data, "open_public", _fake_open)
    monkeypatch.setattr(open_data.time, "sleep", lambda _s: None)
    stats = open_data.collect_all(tmp_path / "evidence", delay=0)
    assert stats["new_captures"] >= 3 and any("FEC skipped" in e for e in stats["errors"])
    manifest = [json.loads(line) for line in (tmp_path / "evidence" / "api-manifest.jsonl").read_text().splitlines()]
    assert all(item["legal_basis"] and item["sha256"] for item in manifest)
    readable = [m for m in manifest if m["method"] == "derived"]
    assert any("$1,500.50" in open(m["raw_file"]).read() for m in readable)
    assert open_data.collect_all(tmp_path / "evidence", delay=0)["new_captures"] == 0


def test_unapproved_host_is_refused(tmp_path):
    with pytest.raises(ValueError):
        open_data.Collector(tmp_path)._request("example.com", None)


def test_api_key_is_never_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("FEC_API_KEY", "SECRETKEY123")
    seen = []

    def fake(request, timeout=30):
        seen.append(request.full_url)
        return FakeResponse(json.dumps({"results": [], "pagination": {"pages": 1}}).encode())

    monkeypatch.setattr(open_data, "open_public", fake)
    monkeypatch.setattr(open_data.time, "sleep", lambda _s: None)
    open_data.Collector(tmp_path / "evidence", 0).fec_contributions()
    assert any("SECRETKEY123" in url for url in seen)
    for path in (tmp_path / "evidence").rglob("*"):
        if path.is_file():
            assert "SECRETKEY123" not in path.read_text()
