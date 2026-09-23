#!/usr/bin/env python3
"""Discover and preserve public pages within explicitly approved official sites."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = "SignalLedgerResearch/0.1 (+lawful-public-records; contact-case-counsel)"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def allowed_by_robots(url: str, cache: dict[str, RobotFileParser]) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        parser = RobotFileParser(f"{origin}/robots.txt")
        try:
            parser.read()
        except (HTTPError, URLError, TimeoutError, OSError):
            return False
        cache[origin] = parser
    return cache[origin].can_fetch(USER_AGENT, url)


def discover(seeds: list[str], output: Path, max_pages: int, max_depth: int, delay: float, max_bytes: int) -> list[dict]:
    queue = deque((url, 0) for url in seeds)
    seen: set[str] = set()
    robots: dict[str, RobotFileParser] = {}
    results: list[dict] = []
    output.mkdir(parents=True, exist_ok=True)
    approved_hosts = {urlparse(seed).netloc for seed in seeds}
    while queue and len(seen) < max_pages:
        url, depth = queue.popleft()
        normalized = url.split("#", 1)[0]
        if normalized in seen:
            continue
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or parsed.netloc not in approved_hosts:
            continue
        seen.add(normalized)
        result: dict[str, object] = {"url": normalized, "depth": depth, "captured_at": datetime.now(timezone.utc).isoformat(), "status": "not-collected"}
        if not allowed_by_robots(normalized, robots):
            result["reason"] = "robots.txt unavailable or disallows this user agent"
            results.append(result)
            continue
        try:
            request = Request(normalized, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"})
            with urlopen(request, timeout=20) as response:
                body = response.read(max_bytes + 1)
                content_type = response.headers.get_content_type()
                if len(body) > max_bytes:
                    result["reason"] = "response exceeded byte limit"
                    results.append(result)
                    continue
            digest = hashlib.sha256(body).hexdigest()
            filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}.bin"
            (output / filename).write_bytes(body)
            result.update({"status": "collected", "http_status": 200, "content_type": content_type, "bytes": len(body), "sha256": digest, "raw_file": str(output / filename)})
            if content_type == "text/html" and depth < max_depth:
                parser = LinkParser()
                parser.feed(body.decode("utf-8", errors="replace"))
                for link in parser.links:
                    child = urljoin(normalized, link).split("#", 1)[0]
                    if urlparse(child).netloc in approved_hosts and child not in seen:
                        queue.append((child, depth + 1))
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            result["reason"] = f"fetch failed: {error}"
        results.append(result)
        time.sleep(max(0, delay))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover public pages within approved official sites.")
    parser.add_argument("seeds", nargs="+", help="Explicit official seed URLs on approved hosts")
    parser.add_argument("--output", type=Path, default=Path("evidence/discovered"))
    parser.add_argument("--manifest", type=Path, default=Path("evidence/discovery-manifest.jsonl"))
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--max-bytes", type=int, default=10_000_000)
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_pages > 500 or args.max_depth < 0 or args.max_depth > 5:
        parser.error("Use max-pages 1-500 and max-depth 0-5.")
    results = discover(args.seeds, args.output, args.max_pages, args.max_depth, args.delay, args.max_bytes)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("a", encoding="utf-8") as manifest:
        for result in results:
            manifest.write(json.dumps(result, sort_keys=True) + "\n")
    print(json.dumps({"visited": len(results), "collected": sum(result["status"] == "collected" for result in results), "manifest": str(args.manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
