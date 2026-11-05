#!/usr/bin/env python3
"""Initialize and launch Signal Ledger on an available loopback port."""
from __future__ import annotations

import argparse
import json
import re
import socket
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from casefile_db import import_case
from server import SignalLedgerHandler
import web_security

PROJECT_ROOT = Path(__file__).resolve().parent


def available_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError("No available local port found in the requested range.")


def new_case(path: Path, title: str, places: list[str]) -> None:
    """Write an empty casefile (no sample data) so a new user can start from a clean slate."""
    template = json.loads((PROJECT_ROOT / "casefile.example.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    case_id = "case-" + (re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "new") + "-" + now.strftime("%Y%m%d")
    case = {key: template[key] for key in ("schema_version", "technical_lenses", "logos", "governance") if key in template}
    case.update({"case_id": case_id, "title": title, "jurisdiction": places, "scope": {"start": "1900-01-01", "end": None, "agencies": [], "record_types": []},
                 "entities": [], "relationships": [], "observations": [], "sources": [], "requests": [], "discrepancies": [],
                 "audit_log": [{"id": "audit-001", "action": "case-created", "actor": "", "timestamp": now.isoformat(), "object_id": case_id, "reason": "", "previous_version": None}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(case, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a local Signal Ledger casefile.")
    parser.add_argument("--casefile", type=Path, default=PROJECT_ROOT / "evidence/casefile.json")
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "evidence/signal-ledger.sqlite")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-protected",
        action="store_true",
        help="Show restricted and counsel-protected evidence in this local session.",
    )
    parser.add_argument("--new-case", metavar="TITLE", help="Create an empty casefile with this title, then start.")
    parser.add_argument("--places", default="", help="Comma-separated places the case covers, used with --new-case.")
    args = parser.parse_args()
    if args.new_case:
        if args.casefile.exists():
            parser.error(f"{args.casefile} already exists; refusing to overwrite it.")
        new_case(args.casefile, args.new_case.strip(), [p.strip() for p in args.places.split(",") if p.strip()])
        print(f"Created {args.casefile}")
    if not args.casefile.is_file():
        parser.error(
            f"Casefile not found: {args.casefile}. Create one with: "
            "python3 run_local.py --new-case \"My case title\" --places \"Town, County, State\"  "
            "(do not use the example casefile as real evidence)."
        )
    args.database.parent.mkdir(parents=True, exist_ok=True)
    import_case(args.database, args.casefile)
    port = available_port(args.port)
    SignalLedgerHandler.database = args.database
    SignalLedgerHandler.port = port
    SignalLedgerHandler.registry = PROJECT_ROOT / "source_registry.json"
    SignalLedgerHandler.search_database = PROJECT_ROOT / "evidence/search.sqlite"
    SignalLedgerHandler.targets = PROJECT_ROOT / "targets.txt"
    SignalLedgerHandler.visible_levels = (
        web_security.ALL_LEVELS if args.allow_protected else web_security.PUBLIC_LEVELS
    )
    handler = partial(SignalLedgerHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Signal Ledger running at http://127.0.0.1:{port}")
    print("Access is limited to this computer. Do not expose this server to the network.")
    if args.allow_protected:
        print("Restricted and counsel-protected evidence is visible in this session.")
    else:
        print("Protected evidence is hidden. Restart with --allow-protected to review it.")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
