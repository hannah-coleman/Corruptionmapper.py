#!/usr/bin/env python3
"""Local read-only web server for Signal Ledger casefile data."""
from __future__ import annotations

import argparse
import cgi
import json
import sqlite3
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class SignalLedgerHandler(SimpleHTTPRequestHandler):
    database: Path
    search_database: Path = Path("evidence/search.sqlite")
    registry: Path = Path("source_registry.json")
    public_files = {"/", "/index.html", "/app.js", "/app-professional.js", "/style.css", "/style-professional.css"}

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route.endswith(('.js', '.css')):
            self.serve_static_file(route)
            return
        if route.startswith("/api/"):
            self.send_api(route)
            return
        if route not in self.public_files:
            self.send_error(404, "Not found")
            return
        super().do_GET()

    def serve_static_file(self, route: str) -> None:
        file_path = Path(route.lstrip('/'))
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return
        mime_type = "text/javascript" if route.endswith('.js') else "text/css"
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_error(500, "Server error")

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/collect":
            self.collect_from_web()
            return
        if route == "/api/collect-approved":
            self.collect_approved_sources()
            return
        if route == "/api/evidence":
            self.save_evidence_record()
            return
        if route == "/api/evidence-upload":
            self.save_uploaded_evidence()
            return
        if route == "/api/claims":
            self.save_claim_record()
            return
        if route == "/api/backup":
            self.create_backup()
            return
        if route == "/api/harden-evidence":
            self.harden_evidence()
            return
        if route == "/api/request-queue":
            self.save_request_record()
            return
        if route.startswith("/api/requests/") and route.endswith("/response-evidence"):
            self.link_request_response_evidence(route)
            return
        if route.startswith("/api/claims/") and route.endswith("/review"):
            self.review_claim_record(route)
            return
        self.send_error(405, "Method not allowed")

    def send_api(self, route: str) -> None:
        if not self.database.exists():
            self.send_json({"error": "Casefile database not found. Initialize it first."}, 404)
            return
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            query = parse_qs(urlparse(self.path).query)
            if route == "/api/health":
                payload = {"status": "ok", "database": str(self.database)}
            elif route == "/api/source-catalog":
                payload = json.loads(self.registry.read_text(encoding="utf-8")) if self.registry.exists() else []
            elif route == "/api/search":
                term = query.get("q", [""])[0].strip()
                if not term:
                    payload = []
                else:
                    pattern = f"%{term}%"
                    payload = [dict(row) for row in connection.execute(
                        "SELECT id, label AS title, 'entity' AS result_type, summary AS detail, entity_type AS category, status AS confidence FROM entities WHERE label LIKE ? OR summary LIKE ? "
                        "UNION ALL SELECT id, title, 'source', issuer_or_account, source_family, type FROM sources WHERE title LIKE ? OR issuer_or_account LIKE ? "
                        "UNION ALL SELECT id, id, 'observation', text, category, confidence FROM observations WHERE text LIKE ? "
                        "UNION ALL SELECT id, message, 'discrepancy', message, kind, severity FROM discrepancies WHERE message LIKE ? ORDER BY result_type, title",
                        (pattern, pattern, pattern, pattern, pattern, pattern))]
            elif route == "/api/search-text":
                term = query.get("q", [""])[0].strip()
                payload = []
                if term:
                    search_connection = sqlite3.connect(self.search_database)
                    search_connection.row_factory = sqlite3.Row
                    try:
                        safe_term = '"' + term.replace('"', '""') + '"'
                        payload = [dict(row) for row in search_connection.execute(
                            "SELECT url, title, source_family, captured_at, raw_file, sha256, snippet(documents, 2, '<mark>', '</mark>', '...', 24) AS excerpt FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT 25",
                            (safe_term,))]
                    except Exception:
                        payload = []
                    finally:
                        search_connection.close()
            elif route == "/api/case":
                row = connection.execute("SELECT * FROM cases ORDER BY id LIMIT 1").fetchone()
                payload = dict(row) if row else {"error": "No case found"}
            elif route == "/api/discrepancies":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, kind, severity, message, disposition, recommended_desks_json, routing_rationale, next_action FROM discrepancies ORDER BY severity DESC, id"
                )]
            elif route == "/api/requests":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, jurisdiction, custodian, description, status, submitted_at, deadline, response_at, denial_reason, counsel_review FROM requests ORDER BY id"
                )]
            elif route == "/api/evidence-live":
                from evidence_store import load_evidence_records
                payload = load_evidence_records(Path("evidence/records.json"))
            elif route == "/api/claims":
                from claim_store import load_claims
                payload = load_claims(Path("evidence/claims.json"))
            elif route == "/api/research-queue":
                from claim_store import load_claims, research_queue
                payload = research_queue(load_claims(Path("evidence/claims.json")))
            elif route == "/api/counsel-packet":
                from claim_store import load_claims
                from counsel_packet import build_counsel_packet
                from evidence_store import load_evidence_records
                payload = build_counsel_packet(
                    load_claims(Path("evidence/claims.json")),
                    load_evidence_records(Path("evidence/records.json")),
                )
                from audit_log import append_entry
                append_entry(Path("evidence/audit.jsonl"), "counsel-packet-generated", details={"findings": len(payload["findings"]), "open_questions": len(payload["open_questions"]), "sources": len(payload["source_index"])})
            elif route == "/api/counsel-packet-print":
                from claim_store import load_claims
                from counsel_packet import build_counsel_packet
                from evidence_store import load_evidence_records
                from packet_render import render_packet
                packet = build_counsel_packet(
                    load_claims(Path("evidence/claims.json")),
                    load_evidence_records(Path("evidence/records.json")),
                )
                from audit_log import append_entry
                append_entry(Path("evidence/audit.jsonl"), "printable-packet-generated", details={"findings": len(packet["findings"]), "open_questions": len(packet["open_questions"]), "sources": len(packet["source_index"])})
                self.send_html(render_packet(packet))
                return
            elif route == "/api/collection-audit":
                from collection_audit import audit_manifest, load_manifest
                payload = audit_manifest(load_manifest(Path("evidence/manifest.jsonl")))
            elif route == "/api/source-changes":
                from collection_audit import detect_source_changes, load_manifest
                payload = detect_source_changes(load_manifest(Path("evidence/manifest.jsonl")))
            elif route == "/api/source-diff":
                from collection_audit import compare_captures, load_manifest
                url = query.get("url", [""])[0].strip()
                if not url:
                    self.send_json({"error": "A source URL is required."}, 400)
                    return
                payload = compare_captures(load_manifest(Path("evidence/manifest.jsonl")), url, Path("evidence"))
            elif route == "/api/timeline":
                from claim_store import load_claims
                from collection_audit import load_manifest
                from evidence_store import load_evidence_records
                from timeline import build_timeline
                payload = build_timeline(
                    load_evidence_records(Path("evidence/records.json")),
                    load_claims(Path("evidence/claims.json")),
                    load_manifest(Path("evidence/manifest.jsonl")),
                )
            elif route == "/api/audit-status":
                from audit_log import read_entries, verify_log
                verification = verify_log(Path("evidence/audit.jsonl"))
                payload = {**verification, "recent_entries": read_entries(Path("evidence/audit.jsonl"))[-12:]}
            elif route == "/api/backup-status":
                from backup import verify_backup
                backups = sorted(Path("backups").glob("signal-ledger-backup-*.zip"))
                payload = verify_backup(backups[-1]) if backups else {"valid": False, "files": 0, "issues": ["No backup has been created yet."]}
            elif route == "/api/security-status":
                from security_audit import assess_evidence_permissions
                payload = assess_evidence_permissions(Path("evidence"))
            elif route == "/api/request-queue":
                from request_queue import list_requests
                payload = list_requests(Path("evidence/requests.json"))
            elif route == "/api/request-deadlines":
                from request_queue import deadline_status, list_requests
                payload = deadline_status(list_requests(Path("evidence/requests.json")), datetime.now(timezone.utc).date().isoformat())
            elif route == "/api/sources":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, title, issuer_or_account, url, source_family, access_method, sensitivity, storage_zone, published_at, captured_at, type FROM sources ORDER BY captured_at DESC, id"
                )]
            elif route == "/api/observations":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, category, sensitivity, storage_zone, lane, text, event_date, location, confidence, next_test FROM observations ORDER BY event_date, id"
                )]
            elif route == "/api/entities":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, label, entity_type, sensitivity, storage_zone, status, summary, x, y FROM entities ORDER BY label"
                )]
            elif route == "/api/relationships":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, source_entity_id, target_entity_id, relation, evidence_status, source_ids_json FROM relationships ORDER BY id"
                )]
            else:
                payload = {"error": "Unknown API route"}
                self.send_json(payload, 404)
                return
            self.send_json(payload)
        finally:
            connection.close()

    def collect_from_web(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            payload = {}
        urls = payload.get("urls", []) if isinstance(payload, dict) else []
        if not isinstance(urls, list) or not urls:
            self.send_json({"error": "No URLs provided."}, 400)
            return
        from collector import collect_urls
        output_dir = Path("evidence/raw")
        results = collect_urls(urls, output_dir, max_bytes=10_000_000, delay=0.0)
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "collection-run", details={"source": "manual-url-list", "targets": len(urls), "collected": sum(item.get("status") == "collected" for item in results)})
        self.send_json({"status": "ok", "results": results})

    def collect_approved_sources(self) -> None:
        from collector import collect_urls, read_urls
        targets_path = Path("targets.txt")
        if not targets_path.exists():
            self.send_json({"error": "Approved target list not found."}, 404)
            return
        urls = read_urls(targets_path)
        results = collect_urls(urls, Path("evidence/raw"), max_bytes=10_000_000, delay=1.0)
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "collection-run", details={"source": "approved-targets", "targets": len(urls), "collected": sum(item.get("status") == "collected" for item in results)})
        self.send_json({"status": "ok", "scope": "approved-targets.txt", "results": results})

    def save_evidence_record(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON body."}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"error": "Evidence payload must be an object."}, 400)
            return
        from evidence_store import save_evidence_record
        record = save_evidence_record(Path("evidence/records.json"), payload)
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "evidence-created", record["id"], {"protection": record.get("protection", "")})
        self.send_json({"status": "ok", "record": record})

    def save_uploaded_evidence(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"error": "Expected a file upload."}, 400)
            return
        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
            )
            uploaded = form["file"] if "file" in form else None
            if uploaded is None or not uploaded.filename:
                self.send_json({"error": "Select a file to preserve."}, 400)
                return
            content = uploaded.file.read(25_000_001)
            metadata = {key: form.getfirst(key, "") for key in ("title", "summary", "kind", "protection")}
            from evidence_store import save_uploaded_evidence
            record = save_uploaded_evidence(
                Path("evidence/records.json"), Path("evidence/uploads"), uploaded.filename, content, metadata
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "file-preserved", record["id"], {"sha256": record["sha256"], "size_bytes": record["size_bytes"], "protection": record["protection"]})
        self.send_json({"status": "ok", "record": record})

    def save_claim_record(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON body."}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"error": "Claim payload must be an object."}, 400)
            return
        try:
            from claim_store import save_claim
            record = save_claim(Path("evidence/claims.json"), payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "claim-created", record["id"], {"status": record["status"], "source_count": len(record["source_ids"])})
        self.send_json({"status": "ok", "record": record})

    def create_backup(self) -> None:
        from backup import create_backup
        backup = create_backup(Path("evidence"), Path("backups"))
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "backup-created", details={"archive": Path(backup["archive"]).name, "files": backup["files"], "manifest_sha256": backup["manifest_sha256"]})
        self.send_json({"status": "ok", "backup": backup})

    def harden_evidence(self) -> None:
        try:
            from security_audit import harden_evidence_permissions
            result = harden_evidence_permissions(Path("evidence"))
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "evidence-permissions-hardened", details={"checked": result["checked"]})
        self.send_json({"status": "ok", "security": result})

    def save_request_record(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid request payload."}, 400)
            return
        try:
            from request_queue import add_request
            record = add_request(Path("evidence/requests.json"), payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "records-request-created", record["id"], {"agency": record["agency"], "status": record["status"]})
        self.send_json({"status": "ok", "record": record})

    def link_request_response_evidence(self, route: str) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            request_id = route.removeprefix("/api/requests/").removesuffix("/response-evidence")
            evidence_id = str(payload.get("evidence_id", "")).strip()
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid response-evidence payload."}, 400)
            return
        from evidence_store import load_evidence_records
        if not evidence_id or evidence_id not in {record.get("id") for record in load_evidence_records(Path("evidence/records.json"))}:
            self.send_json({"error": "Preserved evidence record not found."}, 404)
            return
        try:
            from request_queue import link_response_evidence
            request = link_response_evidence(Path("evidence/requests.json"), request_id, evidence_id)
        except ValueError as error:
            self.send_json({"error": str(error)}, 404)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "request-response-linked", request_id, {"evidence_id": evidence_id})
        self.send_json({"status": "ok", "record": request})

    def review_claim_record(self, route: str) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            claim_id = route.removeprefix("/api/claims/").removesuffix("/review")
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid review payload."}, 400)
            return
        try:
            from claim_store import review_claim
            record = review_claim(Path("evidence/claims.json"), claim_id, payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "claim-reviewed", claim_id, {"disposition": record["review_status"], "status": record["status"]})
        self.send_json({"status": "ok", "record": record})

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content: str, status: int = 200) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Signal Ledger server.")
    parser.add_argument("--database", type=Path, default=Path("evidence/signal-ledger.sqlite"))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--registry", type=Path, default=Path("source_registry.json"))
    parser.add_argument("--search-database", type=Path, default=Path("evidence/search.sqlite"))
    args = parser.parse_args()
    SignalLedgerHandler.database = args.database
    SignalLedgerHandler.registry = args.registry
    SignalLedgerHandler.search_database = args.search_database
    server = ThreadingHTTPServer(("127.0.0.1", args.port), SignalLedgerHandler)
    print(f"Signal Ledger running at http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
