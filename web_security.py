"""Request-trust, URL-scope, and visibility helpers for the local Signal Ledger server."""
from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path
from urllib.parse import urlparse

CSRF_HEADER = "X-Signal-Ledger"
MAX_JSON_BODY = 1_000_000
MAX_UPLOAD_BODY = 26_000_000
PUBLIC_LEVELS = frozenset({"public", "public-graph"})
ALL_LEVELS = None


def local_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}


def host_allowed(host_header: str | None, port: int) -> bool:
    """Reject unexpected Host headers, which blocks DNS-rebinding against the local server."""
    return (host_header or "").lower() in local_hosts(port)


def origin_allowed(origin: str | None, host_header: str | None) -> bool:
    """Browsers send Origin on cross-site POSTs; accept only the server's own origin."""
    if not origin:
        return True
    return origin.lower() == f"http://{(host_header or '').lower()}"


def is_public_address(host: str) -> bool:
    """True only when every address the host resolves to is publicly routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            return False
    return True


def approved_hosts(targets_path: Path, registry_path: Path | None = None) -> set[str]:
    hosts: set[str] = set()
    if targets_path.exists():
        for line in targets_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                host = urlparse(line).hostname
                if host:
                    hosts.add(host.lower())
    if registry_path and registry_path.exists():
        try:
            entries = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
        for entry in entries if isinstance(entries, list) else []:
            for value in entry.values() if isinstance(entry, dict) else []:
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    host = urlparse(value).hostname
                    if host:
                        hosts.add(host.lower())
    return hosts


def url_in_scope(url: object, hosts: set[str]) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in hosts


def visible(records: list[dict], levels: frozenset[str] | None, *keys: str) -> list[dict]:
    """Drop records whose protection level is not allowed; unlabeled records fail closed."""
    if levels is ALL_LEVELS:
        return records
    key_order = keys or ("protection",)

    def level(record: dict) -> str:
        for key in key_order:
            if record.get(key):
                return str(record[key]).lower()
        return "unclassified"

    return [record for record in records if level(record) in levels]
