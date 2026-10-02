import json
import sqlite3
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import server
import web_security
from casefile_db import SCHEMA


@pytest.fixture
def running(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "records.json").write_text(json.dumps([
        {"id": "pub", "title": "Public", "protection": "public"},
        {"id": "res", "title": "Restricted", "protection": "restricted"},
        {"id": "unl", "title": "Unlabeled"},
    ]), encoding="utf-8")
    database = tmp_path / "ledger.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    connection.execute("INSERT INTO cases VALUES ('c', '1', 't', NULL, '[]', '[]')")
    connection.execute("INSERT INTO entities VALUES ('e1', 'c', 'Open Office', 'Government', 'public', 'public-graph', 'fact', 'visible', 0, 0)")
    connection.execute("INSERT INTO entities VALUES ('e2', 'c', 'Protected Witness', 'Person', 'restricted', 'restricted-vault', 'fact', 'hidden', 0, 0)")
    connection.execute("INSERT INTO relationships VALUES ('r1', 'c', 'e1', 'e2', 'contacted', 'fact', '[]')")
    connection.commit()
    connection.close()
    targets = tmp_path / "targets.txt"
    targets.write_text("https://www.sos.arkansas.gov/\n", encoding="utf-8")

    handler = server.SignalLedgerHandler
    saved = (getattr(handler, "database", None), handler.port, handler.targets, handler.visible_levels)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    handler.database, handler.port, handler.targets = database, port, targets
    handler.visible_levels = web_security.PUBLIC_LEVELS
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield port, tmp_path
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)
    handler.database, handler.port, handler.targets, handler.visible_levels = saved


def request(port, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", port)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


TRUSTED = {"X-Signal-Ledger": "1", "Content-Type": "application/json"}


def test_static_serving_is_limited_to_the_allowlist(running):
    port, tmp_path = running
    (tmp_path.parent / "outside-probe.js").write_text("// secret", encoding="utf-8")
    (tmp_path / "other.js").write_text("// not listed", encoding="utf-8")
    assert request(port, "GET", "/../outside-probe.js")[0] == 404
    assert request(port, "GET", "/%2e%2e/outside-probe.js")[0] == 404
    assert request(port, "GET", "/other.js")[0] == 404


def test_unexpected_host_header_is_rejected(running):
    port, _ = running
    assert request(port, "GET", "/api/health", headers={"Host": "evil.example"})[0] == 403
    assert request(port, "GET", "/api/health")[0] == 200


def test_posts_require_csrf_header_and_same_origin(running):
    port, _ = running
    assert request(port, "POST", "/api/backup")[0] == 403
    assert request(port, "POST", "/api/backup", headers={"Origin": "http://evil.example", **TRUSTED})[0] == 403


def test_oversized_json_body_is_rejected(running):
    port, _ = running
    status, _ = request(port, "POST", "/api/claims", body=b"{}", headers={**TRUSTED, "Content-Length": "5000000"})
    assert status == 400


def test_collect_rejects_urls_outside_approved_scope(running):
    port, _ = running
    payload = json.dumps({"urls": ["http://169.254.169.254/latest/meta-data/"]})
    status, data = request(port, "POST", "/api/collect", body=payload, headers=TRUSTED)
    assert status == 400
    assert "approved" in json.loads(data)["error"]


def test_protected_material_is_withheld_by_default(running):
    port, _ = running
    evidence = json.loads(request(port, "GET", "/api/evidence-live")[1])
    assert [r["id"] for r in evidence] == ["pub"]
    entities = json.loads(request(port, "GET", "/api/entities")[1])
    assert [e["id"] for e in entities] == ["e1"]
    assert json.loads(request(port, "GET", "/api/relationships")[1]) == []
    assert json.loads(request(port, "GET", "/api/search?q=Protected")[1]) == []
    assert len(json.loads(request(port, "GET", "/api/search?q=Open")[1])) == 1


def test_upload_roundtrip_preserves_file_and_hash(running):
    port, tmp_path = running
    boundary = "XBOUNDARYX"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"title\"\r\n\r\nMinutes\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"../minutes.txt\"\r\nContent-Type: text/plain\r\n\r\nhello bytes\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    headers = {"X-Signal-Ledger": "1", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    status, data = request(port, "POST", "/api/evidence-upload", body=body, headers=headers)
    assert status == 200, data
    record = json.loads(data)["record"]
    assert record["title"] == "Minutes"
    assert record["protection"] == "restricted"
    assert record["original_filename"] == "minutes.txt"
    assert Path(record["stored_file"]).read_bytes() == b"hello bytes"
