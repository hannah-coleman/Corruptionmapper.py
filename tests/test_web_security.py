from web_security import approved_hosts, host_allowed, is_public_address, origin_allowed, url_in_scope, visible


def test_host_and_origin_checks():
    assert host_allowed("127.0.0.1:8000", 8000)
    assert host_allowed("localhost:8000", 8000)
    assert not host_allowed("evil.example:8000", 8000)
    assert not host_allowed(None, 8000)
    assert origin_allowed(None, "127.0.0.1:8000")
    assert origin_allowed("http://127.0.0.1:8000", "127.0.0.1:8000")
    assert not origin_allowed("http://evil.example", "127.0.0.1:8000")


def test_non_public_addresses_are_rejected():
    for host in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1", ""):
        assert not is_public_address(host)


def test_url_scope_uses_targets_and_registry(tmp_path):
    targets = tmp_path / "targets.txt"
    targets.write_text("# comment\nhttps://www.sos.arkansas.gov/\n", encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text('[{"id": "x", "url": "https://transparency.arkansas.gov/"}]', encoding="utf-8")
    hosts = approved_hosts(targets, registry)
    assert url_in_scope("https://www.sos.arkansas.gov/page", hosts)
    assert url_in_scope("https://transparency.arkansas.gov/", hosts)
    assert not url_in_scope("http://169.254.169.254/latest", hosts)
    assert not url_in_scope("file:///etc/passwd", hosts)
    assert not url_in_scope(["https://www.sos.arkansas.gov/"], hosts)


def test_visibility_fails_closed_for_unlabeled_records():
    records = [{"id": "a", "protection": "public"}, {"id": "b", "protection": "restricted"}, {"id": "c"}, {"id": "d", "protection": "counsel"}]
    assert [r["id"] for r in visible(records, frozenset({"public"}))] == ["a"]
    assert len(visible(records, None)) == 4
