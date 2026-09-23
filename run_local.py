#!/usr/bin/env python3
"""Initialize and launch Signal Ledger on an available loopback port."""
from __future__ import annotations

import argparse
import socket
from pathlib import Path

from casefile_db import import_case
from server import SignalLedgerHandler
from http.server import ThreadingHTTPServer


def available_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError("No available local port found in the requested range.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a local Signal Ledger casefile.")
    parser.add_argument("--casefile", type=Path, default=Path("casefile.example.json"))
    parser.add_argument("--database", type=Path, default=Path("evidence/signal-ledger.sqlite"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    import_case(args.database, args.casefile)
    port = available_port(args.port)
    SignalLedgerHandler.database = args.database
    SignalLedgerHandler.registry = Path("source_registry.json")
    server = ThreadingHTTPServer(("127.0.0.1", port), SignalLedgerHandler)
    print(f"Signal Ledger running at http://127.0.0.1:{port}")
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
