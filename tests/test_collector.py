import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from collector import collect_urls


class _StaticHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = b"<html><body>Public record body</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


def test_collect_urls_records_manifest_and_results(tmp_path):
    server = HTTPServer(("127.0.0.1", 0), _StaticHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        results = collect_urls([f"http://{host}:{port}/page"], tmp_path / "raw", max_bytes=50_000, allow_private_hosts=True)
        manifest_path = tmp_path / "raw" / "../manifest.jsonl"
        assert len(results) == 1
        assert results[0]["status"] == "collected"
        assert results[0]["bytes"] > 0
        assert manifest_path.exists()
        lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
        payload = json.loads(lines[0])
        assert payload["status"] == "collected"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_collect_refuses_loopback_by_default(tmp_path):
    results = collect_urls(["http://127.0.0.1:9/page"], tmp_path / "raw", max_bytes=50_000)
    assert results[0]["status"] == "not-collected"
    assert "publicly routable" in results[0]["reason"]


class _RobotsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"User-agent: *\nDisallow: /private\nCrawl-delay: 7\n" if self.path == "/robots.txt" else b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def test_fetch_robots_uses_rules_and_crawl_delay():
    from collector import USER_AGENT, fetch_robots

    server = HTTPServer(("127.0.0.1", 0), _RobotsHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        parser = fetch_robots(f"http://{host}:{port}/page", allow_private_hosts=True)
        assert parser.can_fetch(USER_AGENT, f"http://{host}:{port}/page")
        assert not parser.can_fetch(USER_AGENT, f"http://{host}:{port}/private/x")
        assert parser.crawl_delay(USER_AGENT) == 7
        assert fetch_robots(f"http://{host}:{port}/page") is None  # loopback refused without opt-in
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
