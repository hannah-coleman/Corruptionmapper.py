#!/usr/bin/env python3
"""Local read-only web server for Signal Ledger casefile data."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import HTTP as HTTP_POLICY
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from collector import collect_urls
from evidence_store import load_evidence_records
import web_security
from review_engine import ReviewEngine

class SignalLedgerHandler(SimpleHTTPRequestHandler):
    database: Path
    search_database: Path = Path("evidence/search.sqlite")
    registry: Path = Path("source_registry.json")
    port: int = 8000
    targets: Path = Path("targets.txt")
    # Protection levels this server may expose; evidence labeled otherwise (or unlabeled) is withheld.
    visible_levels = web_security.PUBLIC_LEVELS
    public_files = {"/", "/index.html", "/app-professional.js", "/style.css", "/style-professional.css", "/map.html", "/map.js", "/start.html", "/start.js", "/layoffs.html", "/layoffs.js", "/cases.html", "/cases.js"}

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if not web_security.host_allowed(self.headers.get("Host"), self.port):
            self.send_error(403, "Unexpected Host header")
            return
        if route in self.public_files:
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
        filename = "index.html" if route == "/" else route.lstrip("/")
        file_path = Path(__file__).resolve().parent / filename
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return
        mime_type = {
            ".html": "text/html",
            ".js": "text/javascript",
            ".css": "text/css",
        }.get(file_path.suffix, "application/octet-stream")
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

    def request_is_trusted(self) -> bool:
        host = self.headers.get("Host")
        return (
            web_security.host_allowed(host, self.port)
            and web_security.origin_allowed(self.headers.get("Origin"), host)
            and self.headers.get(web_security.CSRF_HEADER) == "1"
        )

    def read_body(self, limit: int = web_security.MAX_JSON_BODY) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length.") from error
        if length < 0 or length > limit:
            raise ValueError(f"Request body exceeds the {limit} byte limit.")
        return self.rfile.read(length) if length else b""

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if not self.request_is_trusted():
            self.send_json({"error": "Cross-site or untrusted request rejected."}, 403)
            return
        if route == "/api/collect":
            self.collect_from_web()
            return
        if route == "/api/collect-approved":
            self.collect_approved_sources()
            return
        if route == "/api/autopopulate":
            self.send_json({"status": "ok", "summary": self.run_autopopulate()})
            return
        if route == "/api/historical-archive-search":
            self.search_historical_archives()
            return
        if route == "/api/evidence":
            self.save_evidence_record()
            return
        if route == "/api/evidence-upload":
            self.save_uploaded_evidence()
            return
        if route == "/api/statements":
            try:
                from public_statements import save_statement
                record = save_statement(Path("evidence/statements.json"), self.read_json_object())
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json({"status": "ok", "record": record})
            return
        if route == "/api/references":
            try:
                from reference_register import save_reference
                record = save_reference(Path("evidence/references.json"), self.read_json_object())
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json({"status": "ok", "record": record})
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
        if route.startswith("/api/discrepancies/") and route.endswith("/verify"):
            self.verify_lead(route)
            return
        if route == "/api/places" or route == "/api/places/import":
            try:
                import property_map
                payload = self.read_json_object()
                if route == "/api/places":
                    result = {"status": "ok", "record": property_map.add_place(Path("evidence/places.json"), payload)}
                else:
                    result = {"status": "ok", **property_map.import_csv(Path("evidence/places.json"), str(payload.get("csv", "")))}
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json(result)
            return
        if route in {"/api/case-review/entries", "/api/case-review/consent", "/api/case-review/policy-request"}:
            try:
                import case_review
                payload = self.read_json_object()
                store = Path("evidence/case-review.json")
                if route.endswith("/policy-request"):
                    from lead_actions import policy_request
                    from request_queue import add_request
                    queued = add_request(Path("evidence/request-queue.json"), policy_request(str(payload.get("agency", ""))))
                    result = {"status": "ok", "request_id": queued["id"]}
                elif route.endswith("/entries"):
                    entry = case_review.add_entry(store, payload)
                    result = {"status": "ok", "record": {k: entry[k] for k in ("id", "case_id", "kind", "title")}}
                else:
                    result = {"status": "ok", "person": case_review.set_consent(store, str(payload.get("name", "")), bool(payload.get("named_ok")))}
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json(result)
            return
        if route in {"/api/layoffs", "/api/layoffs/import"}:
            try:
                import layoffs
                payload = self.read_json_object()
                table = str(payload.pop("table", ""))
                if route == "/api/layoffs":
                    result = {"status": "ok", "record": layoffs.add(Path("evidence/layoffs.json"), table, payload)}
                else:
                    result = {"status": "ok", **layoffs.import_csv(Path("evidence/layoffs.json"), table, str(payload.get("csv", "")))}
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
                return
            self.send_json(result)
            return
        if route == "/api/jobs/refresh":
            import jobs
            self.send_json({"status": "ok", "job": jobs.submit("refresh", lambda: jobs.run_pipeline(Path("evidence")))})
            return
        if route == "/api/lead-packet":
            from lead_packet import write_packet
            self.send_json({"status": "ok", "path": str(write_packet(Path("evidence")))})
            return
        if route == "/api/facts/extract":
            self.extract_facts_from_source()
            return
        if route == "/api/facts":
            self.add_manual_fact_record()
            return
        if route.startswith("/api/facts/") and route.endswith("/review"):
            self.review_fact_record(route)
            return
        self.send_error(405, "Method not allowed")

    def sql_visibility(self) -> tuple[str, list[str]]:
        levels = self.visible_levels
        if levels is None:
            return "1=1", []
        marks = ",".join("?" * len(levels))
        return f"sensitivity IN ({marks}) AND storage_zone IN ({marks})", [*sorted(levels), *sorted(levels)]

    def visible_records(self, records: list[dict]) -> list[dict]:
        kept = web_security.visible(records, self.visible_levels)
        self.withheld = len(records) - len(kept)
        return kept

    def read_json_object(self) -> dict:
        try:
            payload = json.loads((self.read_body() or b"{}").decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Invalid JSON body.") from error
        if not isinstance(payload, dict):
            raise ValueError("The request body must be a JSON object.")
        return payload

    def load_fact_source(self, payload: dict) -> tuple[list[str], dict, str]:
        from fact_sources import load_captured_source, load_evidence_source
        if payload.get("evidence_id"):
            return load_evidence_source(Path("evidence/records.json"), Path("evidence/uploads"), str(payload["evidence_id"]))
        if payload.get("url"):
            return load_captured_source(self.search_database, Path("evidence"), str(payload["url"]))
        raise ValueError("Provide an evidence_id or a captured page url.")

    def extract_facts_from_source(self) -> None:
        try:
            pages, source, protection = self.load_fact_source(self.read_json_object())
            from facts import extract_from_pages, save_proposed
            facts = extract_from_pages(pages, source, protection)
            summary = save_proposed(Path("evidence/facts.json"), facts)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "facts-extracted", source["ref"][:80], {"source_sha256": source["sha256"], "protection": protection, **summary})
        self.send_json({"status": "ok", "protection": protection, **summary})

    def add_manual_fact_record(self) -> None:
        try:
            payload = self.read_json_object()
            _, source, protection = self.load_fact_source(payload)
            from facts import add_manual_fact
            fact = add_manual_fact(Path("evidence/facts.json"), payload, source, protection)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "fact-entered", fact["id"], {"kind": fact["kind"], "reviewer": fact["reviewer"], "protection": protection})
        self.send_json({"status": "ok", "record": fact})

    def verify_lead(self, route: str) -> None:
        try:
            payload = self.read_json_object()
            from verification import verify_flag

            flag_id = route.removeprefix("/api/discrepancies/").removesuffix("/verify")
            flag = verify_flag(Path("evidence/discrepancy-flags.json"), flag_id, payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        check = flag["verifications"][-1]
        append_entry(Path("evidence/audit.jsonl"), "lead-verified", flag_id, {"reviewer": check["reviewer"], "method": check["method"], "result": check["result"]})
        self.send_json({"status": "ok", "record": flag})

    def review_fact_record(self, route: str) -> None:
        try:
            payload = self.read_json_object()
            from facts import review_fact

            fact_id = route.removeprefix("/api/facts/").removesuffix("/review")
            fact = review_fact(Path("evidence/facts.json"), fact_id, payload)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "fact-reviewed", fact_id, {
            "reviewer": fact["reviewer"],
            "disposition": fact["status"],
        })
        self.send_json({"status": "ok", "record": fact})

    def document_count(self) -> int:
        if not self.search_database.exists():
            return 0
        connection = sqlite3.connect(self.search_database)
        try:
            return connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        except sqlite3.Error:
            return 0
        finally:
            connection.close()

    def captured_documents(self) -> list[dict]:
        if not self.search_database.exists():
            return []
        search_connection = sqlite3.connect(self.search_database)
        search_connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in search_connection.execute("SELECT url, title, content FROM documents")]
        except sqlite3.Error:
            return []
        finally:
            search_connection.close()

    def case_time_range(self) -> str:
        try:
            scope = json.loads(Path("evidence/casefile.json").read_text(encoding="utf-8")).get("scope", {})
            start = datetime.fromisoformat(scope["start"]).strftime("%B %-d, %Y")
            end = scope.get("end")
            return f"{start} to {datetime.fromisoformat(end).strftime('%B %-d, %Y')}" if end else f"{start} to present"
        except (OSError, ValueError, KeyError, TypeError):
            return "the relevant period"

    def send_api(self, route: str) -> None:
        if not self.database.exists():
            self.send_json({"error": "Casefile database not found. Initialize it first."}, 404)
            return
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            query = parse_qs(urlparse(self.path).query)
            vis_sql, vis_params = self.sql_visibility()
            if route == "/api/health":
                payload = {"status": "ok", "database": str(self.database)}
            elif route == "/api/case":
                row = connection.execute("SELECT id, title, created_at FROM cases ORDER BY id LIMIT 1").fetchone()
                if row is None:
                    self.send_json({"error": "No case found"}, 404)
                    return
                payload = dict(row)
            elif route == "/api/source-catalog":
                payload = json.loads(self.registry.read_text(encoding="utf-8")) if self.registry.exists() else []
            elif route == "/api/search":
                term = query.get("q", [""])[0].strip()
                if not term:
                    payload = []
                else:
                    pattern = f"%{term}%"
                    payload = [dict(row) for row in connection.execute(
                        f"SELECT id, label AS title, 'entity' AS result_type, summary AS detail, entity_type AS category, status AS confidence FROM entities WHERE (label LIKE ? OR summary LIKE ?) AND {vis_sql} "
                        f"UNION ALL SELECT id, title, 'source', issuer_or_account, source_family, type FROM sources WHERE (title LIKE ? OR issuer_or_account LIKE ?) AND {vis_sql} "
                        f"UNION ALL SELECT id, id, 'observation', text, category, confidence FROM observations WHERE text LIKE ? AND {vis_sql} "
                        "UNION ALL SELECT id, message, 'discrepancy', message, kind, severity FROM discrepancies WHERE message LIKE ? ORDER by result_type, title",
                        (pattern, pattern, *vis_params, pattern, pattern, *vis_params, pattern, *vis_params, pattern))]
            elif route == "/api/search-text":
                term = query.get("q", [""])[0].strip()
                agency = query.get("agency", [""])[0].strip()
                kind = query.get("kind", [""])[0].strip().lower()
                question_mode = query.get("mode", [""])[0] == "question"
                if question_mode and (len(term) < 3 or len(term) > 400):
                    self.send_json({"error": "Question must be between 3 and 400 characters."}, 400)
                    return
                if question_mode and not self.search_database.exists():
                    self.send_json({"error": "No captured-page search index is available. Index the collected pages first."}, 503)
                    return
                payload = []
                if term and self.search_database.exists():
                    registry = json.loads(self.registry.read_text(encoding="utf-8")) if self.registry.exists() else []
                    hosts = next((entry.get("hosts", []) for entry in registry if entry.get("id") == agency), []) if agency else []
                    if agency and not hosts:
                        self.send_json({"error": "Unknown agency."}, 400)
                        return
                    fts_term = '"' + term.replace('"', '""') + '"'
                    filters, params = [], [fts_term]
                    if hosts:
                        filters.append("(" + " OR ".join("url LIKE ?" for _ in hosts) + ")")
                        params += [f"%://{host}/%" for host in hosts]
                    if kind in {"pdf", "html"}:
                        filters.append("content_type = ?")
                        params.append("application/pdf" if kind == "pdf" else "text/html")
                    where = "".join(f" AND {clause}" for clause in filters)
                    search_connection = sqlite3.connect(self.search_database)
                    search_connection.row_factory = sqlite3.Row
                    try:
                        search_sql = (
                            "SELECT url, title, content_type, captured_at, raw_file, sha256, "
                            "snippet(documents, 2, '<mark>', '</mark>', '...', 24) AS excerpt "
                            f"FROM documents WHERE documents MATCH ?{where} ORDER BY rank LIMIT 50"
                        )
                        if question_mode:
                            stop_words = {"about", "after", "and", "are", "for", "from", "how", "into", "is", "it",
                                          "that", "the", "this", "was", "what", "when", "where", "which", "who", "why", "with"}
                            terms = list(dict.fromkeys(re.findall(r"[a-z0-9]{2,}", term.lower())))
                            terms = [word for word in terms if word not in stop_words] or terms
                            if not terms:
                                self.send_json({"error": "Question needs searchable words."}, 400)
                                return
                            and_query = " AND ".join(f'"{word}"' for word in terms)
                            payload = [dict(row) for row in search_connection.execute(search_sql, [and_query, *params[1:]])]
                            if not payload and len(terms) > 1:
                                or_query = " OR ".join(f'"{word}"' for word in terms)
                                payload = [dict(row) for row in search_connection.execute(search_sql, [or_query, *params[1:]])]
                        else:
                            payload = [dict(row) for row in search_connection.execute(search_sql, params)]
                    except sqlite3.Error as error:
                        self.log_error(f"Text search failed: {error}")
                        if question_mode:
                            self.send_json({"error": "Question search failed. Try again or narrow your question."}, 500)
                            return
                        payload = []
                    finally:
                        search_connection.close()
            elif route == "/api/discrepancies":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, kind, severity, message, disposition, recommended_desks_json, routing_rationale, next_action FROM discrepancies ORDER BY severity DESC, id"
                )]
                from discrepancy_engine import load_flags
                from verification import verification_level
                severity_by_tier = {1: "high", 2: "medium", 3: "low"}
                labels = {"vote-tally": "Roll call vs. announced vote", "not-recorded-present": "Voter not recorded present",
                          "instrument-duplicate": "Duplicate resolution/ordinance number", "instrument-gap": "Missing resolution/ordinance numbers",
                          "statement-amount": "Public statement: figure not in records", "statement-instrument": "Public statement: measure not in records",
                          "agenda-only": "On the agenda, not in the minutes", "no-minutes": "Agenda with no minutes",
                          "date": "Dates differ between sources", "amount": "Amounts differ between sources"}
                payload += [{
                    "id": flag["id"], "kind": labels.get(flag.get("kind"), "Possible conflict"),
                    "severity": severity_by_tier.get(flag.get("tier"), "low"), "tier": flag.get("tier"),
                    "message": flag["message"], "disposition": flag["status"],
                    "next_action": flag.get("next_action", ""), "lead": True,
                    "meeting": (flag.get("link") or {}).get("detail", ""),
                    "text_method": (flag.get("vector") or {}).get("text_method", "text-layer"),
                    "verification": verification_level(flag),
                    "explanations": flag.get("innocent_explanations", []),
                    "evidence": [{"passage": fact.get("passage", ""), "url": (fact.get("source") or {}).get("ref", ""),
                                  "title": (fact.get("source") or {}).get("title", "")} for fact in flag.get("facts", [])],
                } for flag in self.visible_records(load_flags(Path("evidence/discrepancy-flags.json"))) if flag.get("status") == "open"]
            elif route.startswith("/api/jobs/"):
                import jobs
                payload = jobs.get(route.removeprefix("/api/jobs/"))
                if payload is None:
                    self.send_json({"error": "Job not found."}, 404)
                    return
            elif route.startswith("/api/case-review"):
                import case_review
                store = Path("evidence/case-review.json")
                case_id = query.get("case", [""])[0].strip()
                try:
                    if route == "/api/case-review/report":
                        payload = {"markdown": case_review.build_report(store, case_id, redacted=query.get("redact", ["1"])[0] != "0")}
                    elif route == "/api/case-review/people":
                        payload = {"people": case_review._load(store)["people"]}
                    elif case_id:
                        payload = case_review.analyze(store, case_id)
                    else:
                        payload = {"cases": case_review.cases(store), "patterns": case_review.patterns(store)}
                except ValueError as error:
                    self.send_json({"error": str(error)}, 400)
                    return
            elif route == "/api/layoffs":
                import layoffs
                payload = layoffs.report(Path("evidence/layoffs.json"))
            elif route == "/api/home":
                from verification import summary
                from discrepancy_engine import load_flags
                import property_map, layoffs
                from request_queue import list_requests
                reqs = list_requests(Path("evidence/request-queue.json"))
                payload = {"verification": summary(load_flags(Path("evidence/discrepancy-flags.json"))),
                           "requests": {s: sum(1 for r in reqs if r.get("status") == s) for s in {r.get("status", "draft") for r in reqs}},
                           "places": len(property_map.load_places(Path("evidence/places.json"))),
                           "layoff_flags": len(layoffs.report(Path("evidence/layoffs.json"))["flags"]),
                           "documents": self.document_count(),
                           "packet_built": Path("evidence/lead-packet.md").exists()}
            elif route == "/api/places":
                import property_map
                payload = property_map.build_map(Path("evidence/places.json"))
            elif route == "/api/report":
                from network_report import build_report
                payload = {"markdown": build_report(Path("evidence"))}
            elif route == "/api/status":
                from facts import load_facts
                from evidence_store import load_evidence_records
                payload = {
                    "evidence_records": len(self.visible_records(load_evidence_records(Path("evidence/records.json")))),
                    "facts": len(self.visible_records(load_facts(Path("evidence/facts.json")))),
                }
            elif route == "/api/requests":
                payload = [dict(row) for row in connection.execute(
                    "SELECT id, jurisdiction, custodian, description, status, submitted_at, deadline, response_at, denial_reason, counsel_review FROM requests ORDER BY id"
                )]
            elif route == "/api/evidence-live":
                from evidence_store import load_evidence_records
                payload = self.visible_records(load_evidence_records(Path("evidence/records.json")))
            elif route == "/api/facts":
                from facts import load_facts
                status_filter = query.get("status", [""])[0]
                kind_filter = query.get("kind", [""])[0]
                payload = [fact for fact in self.visible_records(load_facts(Path("evidence/facts.json")))
                           if (not status_filter or fact.get("status") == status_filter) and (not kind_filter or fact.get("kind") == kind_filter)]
            elif route == "/api/claims":
                from claim_store import load_claims
                payload = load_claims(Path("evidence/claims.json"))
            elif route == "/api/foia-plan":
                from foia_plan import build_plan
                from request_queue import list_requests
                registry = json.loads(self.registry.read_text(encoding="utf-8")) if self.registry.exists() else []
                payload = {"time_range": self.case_time_range(), "agencies": build_plan(
                    registry, self.captured_documents(), list_requests(Path("evidence/requests.json")), self.case_time_range())}
            elif route == "/api/research-queue":
                from claim_store import load_claims, research_queue
                payload = research_queue(load_claims(Path("evidence/claims.json")))
            elif route == "/api/counsel-packet":
                from claim_store import load_claims
                from counsel_packet import build_counsel_packet
                from evidence_store import load_evidence_records
                payload = build_counsel_packet(
                    load_claims(Path("evidence/claims.json")),
                    self.visible_records(load_evidence_records(Path("evidence/records.json"))),
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
                    self.visible_records(load_evidence_records(Path("evidence/records.json"))),
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
                    self.visible_records(load_evidence_records(Path("evidence/records.json"))),
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
                payload = {"time_range": self.case_time_range(), "agencies": build_plan(
                    registry, self.captured_documents(), list_requests(Path("evidence/requests.json")), self.case_time_range())}
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
                    f"SELECT id, title, issuer_or_account, url, source_family, access_method, sensitivity, storage_zone, published_at, captured_at, type FROM sources WHERE {vis_sql} ORDER BY captured_at DESC, id",
                    vis_params)]
            elif route == "/api/observations":
                payload = [dict(row) for row in connection.execute(
                    f"SELECT id, category, sensitivity, storage_zone, lane, text, event_date, location, confidence, next_test FROM observations WHERE {vis_sql} ORDER BY event_date, id",
                    vis_params)]
            elif route == "/api/entities":
                payload = [dict(row) for row in connection.execute(
                    f"SELECT id, label, entity_type, sensitivity, storage_zone, status, summary, x, y FROM entities WHERE {vis_sql} ORDER BY label",
                    vis_params)]
            elif route == "/api/relationships":
                payload = [dict(row) for row in connection.execute(
                    f"SELECT id, source_entity_id, target_entity_id, relation, evidence_status, source_ids_json FROM relationships "
                    f"WHERE source_entity_id IN (SELECT id FROM entities WHERE {vis_sql}) AND target_entity_id IN (SELECT id FROM entities WHERE {vis_sql}) ORDER BY id",
                    vis_params + vis_params)]
            else:
                payload = {"error": "Unknown API route"}
                self.send_json(payload, 404)
                return
            self.send_json(payload)
        finally:
            connection.close()

    def collect_from_web(self) -> None:
        try:
            body = self.read_body() or b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            payload = {}
        urls = payload.get("urls", []) if isinstance(payload, dict) else []
        if not isinstance(urls, list) or not urls:
            self.send_json({"error": "No URLs provided."}, 400)
            return
        approved_hosts = web_security.approved_hosts(self.targets, self.registry)
        if not all(
            web_security.url_in_scope(url, approved_hosts)
            and web_security.is_public_address(urlparse(url).hostname or "")
            for url in urls
        ):
            self.send_json({"error": "Only URLs within the approved public source scope may be collected."}, 400)
            return
        output_dir = Path("evidence/raw")
        results = collect_urls(urls, output_dir, max_bytes=10_000_000, delay=0.0)
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "collection-run", details={"source": "manual-url-list", "targets": len(urls), "collected": sum(item.get("status") == "collected" for item in results)})
        self.send_json({"status": "ok", "results": results})

    def collect_approved_sources(self) -> None:
        from collector import collect_urls, read_urls
        targets_path = self.targets
        if not targets_path.exists():
            self.send_json({"error": "Approved target list not found."}, 400)
            return
        urls = read_urls(targets_path)
        results = collect_urls(urls, Path("evidence/raw"), max_bytes=10_000_000, delay=1.0)
        from open_data import collect_all
        api_stats = collect_all(Path("evidence"))
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "collection-run", details={"source": "approved-targets", "targets": len(urls), "collected": sum(item.get("status") == "collected" for item in results), "api_new_captures": api_stats["new_captures"]})
        self.send_json({"status": "ok", "results": results, "api": api_stats, "summary": self.run_autopopulate()})

    def search_historical_archives(self) -> None:
        try:
            payload = self.read_json_object()
            from historical_archives import search_archives
            result = search_archives(
                payload.get("query", ""),
                Path("evidence"),
                payload.get("start_date", ""),
                payload.get("end_date", ""),
                payload.get("max_results", 40),
            )
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        if result["pages_preserved"]:
            result["ingest"] = self.run_autopopulate()
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "historical-archive-search", details={
            "archives": [item["archive"] for item in result["archives"]],
            "query": result["query"],
            "pages_searched": sum(item["pages_searched"] for item in result["archives"]),
            "pages_preserved": result["pages_preserved"],
            "catalog_only": result["catalog_only"],
            "errors": len(result["errors"]),
        })
        self.send_json({"status": "ok", "result": result})

    def run_autopopulate(self) -> dict:
        import jobs
        return jobs.run_pipeline(Path("evidence"))

    def save_evidence_record(self) -> None:
        try:
            body = self.read_body() or b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON body."}, 400)
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
            body = self.read_body(web_security.MAX_UPLOAD_BODY)
            message = BytesParser(policy=HTTP_POLICY).parsebytes(b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body)
            parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
            uploaded = parts.get("file")
            filename = uploaded.get_filename() if uploaded is not None else None
            if not filename:
                self.send_json({"error": "Select a file to preserve."}, 400)
                return
            content = uploaded.get_payload(decode=True) or b""
            metadata = {key: (parts[key].get_content() if key in parts else "") for key in ("title", "summary", "kind", "protection")}
            from evidence_store import save_uploaded_evidence
            record = save_uploaded_evidence(
                Path("evidence/records.json"), Path("evidence/uploads"), filename, content, metadata
            )
        except ValueError as error:
            self.send_json({"error": str(error) or "Could not read the upload."}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "file-preserved", record["id"], {"sha256": record["sha256"], "size_bytes": record["size_bytes"], "protection": record["protection"]})
        import jobs
        from user_records import register_for_indexing
        indexing = register_for_indexing(Path("evidence"), record)
        job = jobs.submit("refresh", lambda: jobs.run_pipeline(Path("evidence"))) if indexing["indexed"] else None
        self.send_json({"status": "ok", "record": record, "indexing": indexing, "job": job})

    def save_claim_record(self) -> None:
        try:
            body = self.read_body() or b"{}"
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
            pass
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "evidence-permissions-hardened", details={"checked": result["checked"]})
        self.send_json({"status": "ok", "security": result})

    def save_request_record(self) -> None:
        try:
            body = self.read_body() or b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON body."}, 400)
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
            body = self.read_body() or b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            request_id = route.removeprefix("/api/requests/").removesuffix("/response-evidence")
            evidence_id = str(payload.get("evidence_id", "")).strip()
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid JSON body."}, 400)
            return
        if not evidence_id or evidence_id not in {record.get("id") for record in load_evidence_records(Path("evidence/records.json"))}:
            self.send_json({"error": "Preserved evidence record not found."}, 404)
            return
        try:
            from request_queue import link_response_evidence
            request = link_response_evidence(Path("evidence/requests.json"), request_id, evidence_id)
        except ValueError as error:
            self.send_json({"error": "Invalid JSON body."}, 400)
            return
        from audit_log import append_entry
        append_entry(Path("evidence/audit.jsonl"), "request-response-linked", request_id, {"evidence_id": evidence_id})
        self.send_json({"status": "ok", "record": request})

    def review_claim_record(self, route: str) -> None:
        try:
            body = self.read_body() or b"{}"
            payload = json.loads(body.decode("utf-8")) if body else {}
            claim_id = route.removeprefix("/api/claims/").removesuffix("/review")
            engine = ReviewEngine(Path("evidence/claims.json"), Path("evidence/records.json"), Path("evidence/audit.jsonl"))
            record = engine.review_claim(claim_id, payload["reviewer"], payload["disposition"], payload["rationale"], payload["next_action"])
        except (ValueError, KeyError) as error:
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
        if getattr(self, "withheld", 0):
            self.send_header("X-Protected-Withheld", str(self.withheld))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content: str, status: int = 200) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "no-store")
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
    parser.add_argument("--targets", type=Path, default=Path("targets.txt"))
    parser.add_argument("--allow-protected", action="store_true", help="Expose restricted and counsel-protected material (operator decision; no per-user access control yet).")
    args = parser.parse_args()
    SignalLedgerHandler.port = args.port
    SignalLedgerHandler.targets = args.targets
    if args.allow_protected:
        SignalLedgerHandler.visible_levels = web_security.ALL_LEVELS
    SignalLedgerHandler.database = args.database
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