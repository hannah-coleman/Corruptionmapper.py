#!/usr/bin/env python3
"""Collect from documented public open-data APIs, preserving each response with provenance.

Only the hosts in API_SOURCES are contacted. Each is a government or nonprofit service that
publishes a free programmatic API for exactly this kind of public-records use. Nothing here
logs in, bypasses a control, or reads non-public data. API keys come from the environment and
are never written to disk or to the manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request

from collector import USER_AGENT, open_public

API_SOURCES = {
    "api.usaspending.gov": {"family": "federal-agencies", "basis": "Public U.S. Treasury open-data API (no key, no login); award data published under the DATA Act."},
    "projects.propublica.org": {"family": "nonprofit-filings", "basis": "ProPublica Nonprofit Explorer API; republishes public IRS Form 990 data. Attribute ProPublica when quoting."},
    "api.open.fec.gov": {"family": "campaign-finance", "basis": "Federal Election Commission public API; requires a free api.data.gov key supplied by the researcher."},
}
GREENE_COUNTY_AR_FIPS = "055"
MAX_BYTES = 10_000_000


def _money(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "amount not stated"


def render_usaspending(payload: dict) -> str:
    lines = []
    for row in payload.get("results", []):
        lines.append(
            f"Federal award {row.get('Award ID')} to {row.get('Recipient Name')}: {_money(row.get('Award Amount'))} "
            f"awarded by {row.get('Awarding Agency')}, start date {row.get('Start Date')}. {row.get('Description') or ''}".strip())
    return "\n".join(lines)


def render_propublica_search(payload: dict) -> str:
    return "\n".join(
        f"Nonprofit {org.get('name')} (EIN {org.get('ein')}), {org.get('city')}, {org.get('state')}; NTEE {org.get('ntee_code') or 'n/a'}."
        for org in payload.get("organizations", []))


def render_propublica_org(payload: dict) -> str:
    org = payload.get("organization", {})
    lines = [f"Nonprofit {org.get('name')} (EIN {org.get('ein')}), {org.get('city')}, {org.get('state')}."]
    for filing in payload.get("filings_with_data", []):
        lines.append(
            f"{org.get('name')} Form 990 tax year {filing.get('tax_prd_yr')}: revenue {_money(filing.get('totrevenue'))}, "
            f"expenses {_money(filing.get('totfuncexpns'))}, officer compensation {_money(filing.get('compnsatncurrofcr'))}.")
    return "\n".join(lines)


def render_fec(payload: dict) -> str:
    return "\n".join(
        f"FEC contribution of {_money(row.get('contribution_receipt_amount'))} on {row.get('contribution_receipt_date', '')[:10]} "
        f"from {row.get('contributor_name')} ({row.get('contributor_city')}, {row.get('contributor_state')}, employer {row.get('contributor_employer') or 'n/a'}) "
        f"to {row.get('committee', {}).get('name') or row.get('committee_id')}."
        for row in payload.get("results", []))


class Collector:
    def __init__(self, evidence_dir: Path | str = "evidence", delay: float = 1.0) -> None:
        self.dir = Path(evidence_dir)
        self.out = self.dir / "api"
        self.manifest = self.dir / "api-manifest.jsonl"
        self.delay = delay
        self.known = self._known_hashes()
        self.stats = {"requests": 0, "new_captures": 0, "unchanged": 0, "errors": []}

    def _known_hashes(self) -> set[str]:
        if not self.manifest.exists():
            return set()
        hashes = set()
        for line in self.manifest.read_text(encoding="utf-8").splitlines():
            try:
                hashes.add(json.loads(line).get("sha256"))
            except json.JSONDecodeError:
                continue
        return hashes

    def _record(self, label: str, host: str, public_url: str, body: bytes, rendered: str) -> None:
        source = API_SOURCES[host]
        now = datetime.now(timezone.utc)
        digest = hashlib.sha256(body).hexdigest()
        if digest in self.known:
            self.stats["unchanged"] += 1
            return
        self.out.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        raw_path = self.out / f"{stamp}-{digest[:12]}.json"
        raw_path.write_bytes(body)
        entries = [{
            "status": "collected", "url": public_url, "host": host, "method": "API", "label": label,
            "raw_file": str(raw_path), "content_type": "application/json", "sha256": digest, "bytes": len(body),
            "captured_at": now.isoformat(), "source_family": source["family"], "legal_basis": source["basis"],
        }]
        if rendered:
            text = rendered.encode("utf-8")
            text_path = self.out / f"{stamp}-{digest[:12]}.txt"
            text_path.write_bytes(text)
            entries.append({
                "status": "collected", "url": f"{public_url}#readable-rendering", "host": host, "method": "derived",
                "label": f"{label} (readable rendering)", "raw_file": str(text_path), "content_type": "text/plain",
                "sha256": hashlib.sha256(text).hexdigest(), "bytes": len(text), "captured_at": now.isoformat(),
                "source_family": source["family"], "derived_from_sha256": digest, "legal_basis": source["basis"],
            })
        with self.manifest.open("a", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        self.known.add(digest)
        self.stats["new_captures"] += 1

    def _request(self, host: str, request: Request) -> bytes | None:
        if host not in API_SOURCES:
            raise ValueError(f"{host} is not an approved open-data API host.")
        self.stats["requests"] += 1
        try:
            with open_public(request, timeout=30) as response:
                body = response.read(MAX_BYTES + 1)
        except Exception as error:
            self.stats["errors"].append(f"{host}: {type(error).__name__}: {error}")
            return None
        finally:
            time.sleep(self.delay)
        if len(body) > MAX_BYTES:
            self.stats["errors"].append(f"{host}: response exceeded {MAX_BYTES} bytes and was discarded.")
            return None
        return body

    def usaspending_awards(self, start: str, end: str, pages: int = 5) -> None:
        host, url = "api.usaspending.gov", "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        groups = {"contracts": ["A", "B", "C", "D"], "grants": ["02", "03", "04", "05"], "direct-payments": ["06", "10"]}
        for group, codes in groups.items():
            for page in range(1, pages + 1):
                body = json.dumps({
                    "filters": {"time_period": [{"start_date": start, "end_date": end}], "award_type_codes": codes,
                                "place_of_performance_locations": [{"country": "USA", "state": "AR", "county": GREENE_COUNTY_AR_FIPS}]},
                    "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description"],
                    "sort": "Award Amount", "order": "desc", "limit": 100, "page": page,
                }).encode()
                request = Request(url, data=body, method="POST", headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
                raw = self._request(host, request)
                if raw is None:
                    break
                payload = json.loads(raw)
                public_url = f"{url}#request={hashlib.sha256(body).hexdigest()[:10]}"
                self._record(f"USAspending {group} awards in Greene County AR, page {page}", host, public_url, raw, render_usaspending(payload))
                if not payload.get("page_metadata", {}).get("hasNext"):
                    break

    def propublica_nonprofits(self, query: str = "Paragould", state: str = "AR", max_orgs: int = 25) -> None:
        host, base = "projects.propublica.org", "https://projects.propublica.org/nonprofits/api/v2"
        search_url = f"{base}/search.json?{urlencode({'q': query, 'state[id]': state})}"
        raw = self._request(host, Request(search_url, headers={"User-Agent": USER_AGENT}))
        if raw is None:
            return
        payload = json.loads(raw)
        self._record(f"Nonprofit Explorer search: {query}, {state}", host, search_url, raw, render_propublica_search(payload))
        for org in payload.get("organizations", [])[:max_orgs]:
            url = f"{base}/organizations/{int(org['ein'])}.json"
            detail = self._request(host, Request(url, headers={"User-Agent": USER_AGENT}))
            if detail is not None:
                self._record(f"Nonprofit Explorer filings: {org.get('name')}", host, url, detail, render_propublica_org(json.loads(detail)))

    def fec_contributions(self, city: str = "Paragould", state: str = "AR", cycles=(2024, 2026), pages: int = 3) -> None:
        key = os.environ.get("FEC_API_KEY", "").strip()
        if not key:
            self.stats["errors"].append("FEC skipped: set FEC_API_KEY (free key from api.data.gov) to enable campaign-finance collection.")
            return
        host, base = "api.open.fec.gov", "https://api.open.fec.gov/v1/schedules/schedule_a/"
        for cycle in cycles:
            for page in range(1, pages + 1):
                params = {"contributor_city": city, "contributor_state": state, "two_year_transaction_period": cycle,
                          "per_page": 100, "page": page, "sort": "-contribution_receipt_amount"}
                raw = self._request(host, Request(f"{base}?{urlencode({**params, 'api_key': key})}", headers={"User-Agent": USER_AGENT}))
                if raw is None:
                    break
                payload = json.loads(raw)
                self._record(f"FEC contributions from {city}, {state}, cycle {cycle}, page {page}", host, f"{base}?{urlencode(params)}", raw, render_fec(payload))
                if page >= payload.get("pagination", {}).get("pages", 1):
                    break


def collect_all(evidence_dir: Path | str = "evidence", delay: float = 1.0) -> dict:
    evidence_dir = Path(evidence_dir)
    start = "2024-01-01"
    try:
        start = json.loads((evidence_dir / "casefile.json").read_text(encoding="utf-8")).get("scope", {}).get("start") or start
    except (OSError, json.JSONDecodeError):
        pass
    collector = Collector(evidence_dir, delay)
    collector.usaspending_awards(start, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    collector.propublica_nonprofits()
    collector.fec_contributions()
    return collector.stats


if __name__ == "__main__":
    print(json.dumps(collect_all(), indent=2))
