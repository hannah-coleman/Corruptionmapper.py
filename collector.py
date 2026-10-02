#!/usr/bin/env python3
"""Collect explicitly supplied public web records with provenance metadata.

This collector is intentionally narrow: it fetches URLs listed by the researcher,
checks robots.txt, rate-limits requests, and stores an immutable raw response copy.
It does not authenticate, bypass controls, follow links, or discover private data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import HTTPRedirectHandler, Request, build_opener

from web_security import is_public_address

USER_AGENT = "SignalLedgerResearch/0.1 (+lawful-public-records; contact case-counsel)"


def read_urls(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def fetch_robots(url: str, allow_private_hosts: bool = False) -> RobotFileParser | None:
    """Return the host's parsed robots.txt, or None when it cannot be determined (treated as disallowed)."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    if not allow_private_hosts and not is_public_address(parsed.hostname or ""):
        return None
    try:
        with open_public(Request(robots_url, headers={"User-Agent": USER_AGENT}), allow_private_hosts=allow_private_hosts) as response:
            parser.parse(response.read().decode("utf-8", "replace").splitlines())
    except HTTPError as error:
        if error.code in (401, 403):
            parser.parse(["User-agent: *", "Disallow: /"])
        elif 400 <= error.code < 500:
            parser.parse([])
        else:
            return None
    except (URLError, TimeoutError, OSError):
        return None
    return parser


def robots_allows(url: str, allow_private_hosts: bool = False) -> bool:
    parser = fetch_robots(url, allow_private_hosts)
    return parser is not None and parser.can_fetch(USER_AGENT, url)


def open_public(request: Request, timeout: int = 20, allow_private_hosts: bool = False):
    return build_opener(_ScopedRedirectHandler(allow_private_hosts)).open(request, timeout=timeout)


class _ScopedRedirectHandler(HTTPRedirectHandler):
    """Follow redirects only to public HTTP(S) hosts, never to internal addresses."""

    def __init__(self, allow_private_hosts: bool):
        self.allow_private_hosts = allow_private_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlparse(newurl)
        if target.scheme not in {"http", "https"}:
            raise HTTPError(newurl, code, "Redirect to a non-HTTP(S) URL blocked.", headers, fp)
        if not self.allow_private_hosts and not is_public_address(target.hostname or ""):
            raise HTTPError(newurl, code, "Redirect to a non-public host blocked.", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def collect(url: str, output_dir: Path, max_bytes: int, allow_private_hosts: bool = False) -> dict[str, object]:
    captured = datetime.now(timezone.utc)
    parsed = urlparse(url)
    result: dict[str, object] = {
        "url": url,
        "host": parsed.netloc,
        "captured_at": captured.isoformat(),
        "method": "GET",
        "status": "not-collected",
    }
    if parsed.scheme not in {"http", "https"}:
        result["reason"] = "Only HTTP(S) URLs are accepted."
        return result
    if not allow_private_hosts and not is_public_address(parsed.hostname or ""):
        result["reason"] = "Host is not a publicly routable address."
        return result
    if not robots_allows(url, allow_private_hosts):
        result["reason"] = "robots.txt unavailable or disallows this user agent."
        return result

    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"})
    try:
        with open_public(request, allow_private_hosts=allow_private_hosts) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                result["reason"] = f"Response exceeded {max_bytes} byte limit."
                return result
            content_type = response.headers.get_content_type()
            filename = f"{captured.strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(url.encode()).hexdigest()[:12]}.bin"
            raw_path = output_dir / filename
            raw_path.write_bytes(body)
            result.update({
                "status": "collected",
                "http_status": response.status,
                "content_type": content_type,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "raw_file": str(raw_path),
            })
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        result["reason"] = f"Fetch failed: {error}"
    return result


def collect_urls(urls: list[str], output_dir: Path, max_bytes: int = 10_000_000, delay: float = 0.0, allow_private_hosts: bool = False) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir.parent / "manifest.jsonl"
    results: list[dict[str, object]] = []
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for index, url in enumerate(urls):
            result = collect(url, output_dir, max_bytes, allow_private_hosts)
            results.append(result)
            manifest.write(json.dumps(result, sort_keys=True) + "\n")
            if index < len(urls) - 1 and delay > 0:
                time.sleep(delay)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch explicitly listed public records lawfully.")
    parser.add_argument("urls", type=Path, help="Text file containing one public URL per line")
    parser.add_argument("--output", type=Path, default=Path("evidence/raw"), help="Raw evidence directory")
    parser.add_argument("--max-bytes", type=int, default=10_000_000, help="Maximum response size")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    args = parser.parse_args()
    urls = read_urls(args.urls)
    if not urls:
        parser.error("URL list is empty")
    results = collect_urls(urls, args.output, args.max_bytes, args.delay)
    for result in results:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
