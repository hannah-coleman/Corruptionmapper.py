"""Discover and preserve full-text results from public historical archive catalogs."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from urllib.request import Request

from collector import USER_AGENT, open_public

LOC_HOST = "www.loc.gov"
LOC_COLLECTION = f"https://{LOC_HOST}/collections/chronicling-america/"
DIGITAL_ARCHIVE_HOST = "ar-digital.contentdm.oclc.org"
DIGITAL_ARCHIVE_API = f"https://{DIGITAL_ARCHIVE_HOST}/digital/api"
MAX_RESULTS = 100
RESULTS_PER_PAGE = 20
MAX_RESPONSE_BYTES = 10_000_000


def _validate_date(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise ValueError(f"{label} must use YYYY-MM-DD.") from error


def _archive_url(item: dict) -> str:
    value = str(item.get("id") or item.get("url") or "").strip()
    if value.startswith("//"):
        value = f"https:{value}"
    elif value.startswith("/"):
        value = f"https://{LOC_HOST}{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {LOC_HOST, "loc.gov"}:
        return ""
    page_number = parse_qs(parsed.query).get("sp", [])
    query = urlencode({"sp": page_number[0]}) if page_number else ""
    return urlunparse(("https", parsed.netloc, parsed.path, "", query, ""))


def _json_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["fo"] = ["json"]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query, doseq=True), ""))


def _get_json(url: str, host: str = LOC_HOST, source: str = "Library of Congress") -> tuple[dict, bytes]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {host, host.removeprefix("www.")}:
        raise ValueError(f"Archive request was outside the approved {source} host.")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with open_public(request, timeout=30) as response:
        final_url = urlparse(response.geturl())
        if final_url.scheme != "https" or final_url.hostname not in {host, host.removeprefix("www.")}:
            raise ValueError(f"The archive request redirected outside the approved {source} host.")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Archive response exceeded the 10 MB limit.")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{source} returned invalid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{source} returned an unexpected response.")
    return payload, body


def _text_field(payload: dict, key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(part) for part in value).strip()
    return ""


def _write_capture(
    evidence_dir: Path,
    manifest_path: Path,
    item: dict,
    api_body: bytes,
    text: str,
    query: str,
    archive: str,
    host: str,
    page_url: str,
    metadata_url: str,
    source_family: str,
    text_method: str,
    text_label: str,
) -> dict:
    archive_dir = evidence_dir / "historical-archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    title = str(item.get("title") or item.get("date") or "Library of Congress newspaper page")
    captured_at = datetime.now(timezone.utc)
    stamp = captured_at.strftime("%Y%m%dT%H%M%SZ")
    api_hash = hashlib.sha256(api_body).hexdigest()
    api_path = archive_dir / f"{stamp}-{api_hash[:12]}.json"
    api_path.write_bytes(api_body)
    text = re.sub(r"\s+", " ", text).strip()
    text_bytes = text.encode("utf-8")
    text_hash = hashlib.sha256(text_bytes).hexdigest()
    text_path = archive_dir / f"{stamp}-{text_hash[:12]}.txt"
    text_path.write_bytes(text_bytes)
    base = {
        "status": "collected",
        "url": page_url,
        "host": host,
        "captured_at": captured_at.isoformat(),
        "source_family": source_family,
        "archive": archive,
        "archive_title": title,
        "publication_date": str(item.get("date") or ""),
        "search_query": query,
        "legal_basis": (
            "Public Library of Congress JSON API and digitized newspaper OCR."
            if host in {LOC_HOST, "loc.gov"}
            else "Public Arkansas State Archives CONTENTdm API and catalog text."
        ),
        "rights": str(item.get("rights") or ""),
    }
    entries = [
        {
            **base,
            "url": metadata_url or page_url,
            "method": "archive-api-response",
            "label": f"{title} (archive metadata)",
            "raw_file": str(api_path),
            "content_type": "application/json",
            "sha256": api_hash,
            "bytes": len(api_body),
        },
        {
            **base,
            "url": f"{page_url}#source-text" if page_url else LOC_COLLECTION,
            "method": text_method,
            "label": f"{title} ({text_label})",
            "raw_file": str(text_path),
            "content_type": "text/plain",
            "sha256": text_hash,
            "bytes": len(text_bytes),
            "derived_from_sha256": api_hash,
        },
    ]
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for entry in entries:
            manifest.write(json.dumps(entry, sort_keys=True) + "\n")
    return {
        "archive": archive,
        "title": title,
        "date": base["publication_date"],
        "url": page_url,
        "excerpt": text[:600],
        "sha256": text_hash,
    }


def search_chronicling_america(
    query: str,
    evidence_dir: Path | str = "evidence",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 40,
    delay: float = 0.5,
) -> dict:
    """Search digitized U.S. newspaper OCR in Chronicling America and preserve matching pages."""
    term = str(query).strip()
    if len(term) < 3 or len(term) > 250:
        raise ValueError("Search terms must be between 3 and 250 characters.")
    start_date = _validate_date(str(start_date).strip(), "Start date")
    end_date = _validate_date(str(end_date).strip(), "End date")
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date must not be after end date.")
    if not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"Maximum results must be between 1 and {MAX_RESULTS}.")

    evidence_dir = Path(evidence_dir)
    manifest_path = evidence_dir / "historical-archive-manifest.jsonl"
    matches = []
    catalog_only = 0
    date_filtered = 0
    pages = 0
    errors = []
    total_matches = None
    next_url = None

    max_pages = (min(MAX_RESULTS * 5, max_results * 5) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    while pages < max_pages and len(matches) + catalog_only < max_results:
        if next_url:
            request_url = next_url
        else:
            params = {
                "fo": "json",
                "dl": "page",
                "q": term,
                "c": str(min(RESULTS_PER_PAGE, max_results)),
                "sp": "1",
            }
            if start_date or end_date:
                first_year = max(1777, int(start_date[:4])) if start_date else 1777
                last_year = int(end_date[:4]) if end_date else datetime.now(timezone.utc).year
                params["dates"] = f"{first_year}-{last_year}"
            request_url = f"{LOC_COLLECTION}?{urlencode(params)}"
        try:
            payload, _ = _get_json(request_url)
        except (OSError, TimeoutError, ValueError) as error:
            errors.append(f"Library of Congress archive search failed: {error}")
            break
        pages += 1
        pagination = payload.get("pagination") or {}
        if total_matches is None:
            try:
                total_matches = int(pagination.get("total") or payload.get("total") or 0)
            except (TypeError, ValueError):
                total_matches = 0
        items = payload.get("results", [])
        if not isinstance(items, list):
            errors.append("Library of Congress search returned an invalid results list.")
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _in_date_range(str(item.get("date") or ""), start_date, end_date):
                date_filtered += 1
                continue
            detail_payload = item
            api_body = json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")
            text = _text_field(item, "full_text")
            text_method = "archive-ocr" if text else ""
            text_label = "OCR text"
            search_excerpt = _text_field(item, "description")
            if not text:
                page_url = _archive_url(item)
                if page_url:
                    try:
                        detail_payload, api_body = _get_json(_json_url(page_url))
                        text = _text_field(detail_payload, "full_text")
                        if text:
                            text_method = "archive-ocr"
                    except (OSError, TimeoutError, ValueError) as error:
                        errors.append(f"Could not read OCR for {page_url}: {error}")
                    if delay:
                        time.sleep(max(0.0, delay))
            if not text:
                text = _text_field(detail_payload, "description") or search_excerpt
                if text:
                    text_method = "archive-catalog-text"
                    text_label = "catalog text"
            if not text:
                catalog_only += 1
                continue
            metadata = {**item, **detail_payload}
            try:
                page_url = _archive_url(metadata)
                matches.append(_write_capture(
                    evidence_dir, manifest_path, metadata, api_body, text, term,
                    "Library of Congress, Chronicling America", LOC_HOST,
                    page_url, _json_url(page_url) if page_url else LOC_COLLECTION,
                    "historical-newspapers", text_method, text_label,
                ))
            except OSError as error:
                errors.append(f"Could not preserve a newspaper page: {error}")
                break
            if len(matches) + catalog_only >= max_results:
                break
        next_url = pagination.get("next")
        if not next_url or len(matches) + catalog_only >= max_results:
            break
        next_parsed = urlparse(next_url)
        if next_parsed.hostname not in {LOC_HOST, "loc.gov"} or next_parsed.scheme != "https":
            errors.append("Library of Congress returned a pagination link outside its approved host.")
            break
        if delay:
            time.sleep(max(0.0, delay))
    return {
        "archive": "Library of Congress, Chronicling America",
        "query": term,
        "date_range": {"start": start_date or None, "end": end_date or None},
        "publication_scope": "Digitized U.S. newspaper titles; results can include out-of-state mentions and OCR errors.",
        "total_matches": total_matches,
        "pages_searched": pages,
        "pages_preserved": len(matches),
        "catalog_only": catalog_only,
        "date_filtered": date_filtered,
        "has_more": bool(next_url),
        "result_limit": max_results,
        "matches": matches,
        "errors": errors,
    }


def _digital_item_url(alias: str, item_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", alias) or not re.fullmatch(r"\d+", item_id):
        return ""
    return f"https://{DIGITAL_ARCHIVE_HOST}/digital/singleitem/collection/{alias}/id/{item_id}"


def _metadata_values(payload: dict) -> dict[str, str]:
    fields = payload.get("metadataFields", [])
    if not isinstance(fields, list):
        return {}
    return {
        str(field.get("key", "")).lower(): str(field.get("value", "")).strip()
        for field in fields
        if isinstance(field, dict) and field.get("key")
    }


def _in_date_range(value: str, start_date: str, end_date: str) -> bool:
    if not start_date and not end_date:
        return True
    match = re.search(r"\b\d{4}(?:-\d{2}(?:-\d{2})?)?\b", value)
    if not match:
        return True
    date_value = match.group(0)
    if len(date_value) == 4:
        date_value += "-01-01"
    elif len(date_value) == 7:
        date_value += "-01"
    return not (start_date and date_value < start_date or end_date and date_value > end_date)


def search_arkansas_digital_archives(
    query: str,
    evidence_dir: Path | str = "evidence",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 40,
    delay: float = 0.5,
) -> dict:
    """Search all public CONTENTdm collections at the Arkansas State Archives."""
    term = str(query).strip()
    if len(term) < 3 or len(term) > 250:
        raise ValueError("Search terms must be between 3 and 250 characters.")
    start_date = _validate_date(start_date, "Start date")
    end_date = _validate_date(end_date, "End date")
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date must not be after end date.")
    if not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"Maximum results must be between 1 and {MAX_RESULTS}.")

    evidence_dir = Path(evidence_dir)
    manifest_path = evidence_dir / "historical-archive-manifest.jsonl"
    results = []
    catalog_only = 0
    date_filtered = 0
    pages = 0
    errors = []
    total_matches = None
    next_page = 1
    max_pages = (min(MAX_RESULTS * 5, max_results * 5) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    while pages < max_pages and len(results) + catalog_only < max_results:
        search_url = (
            f"{DIGITAL_ARCHIVE_API}/search/collection/all/searchterm/{quote(term, safe='')}"
            f"/maxRecords/{RESULTS_PER_PAGE}/page/{next_page}"
        )
        try:
            payload, _ = _get_json(search_url, DIGITAL_ARCHIVE_HOST, "Arkansas Digital Archives")
        except (OSError, TimeoutError, ValueError) as error:
            errors.append(f"Arkansas Digital Archives search failed: {error}")
            break
        pages += 1
        try:
            total_matches = int(payload.get("totalResults", 0))
        except (TypeError, ValueError):
            total_matches = 0
        items = payload.get("items", [])
        if not isinstance(items, list):
            errors.append("Arkansas Digital Archives returned an invalid results list.")
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            alias = str(item.get("collectionAlias", "")).strip()
            item_id = str(item.get("itemId", "")).strip()
            item_url = _digital_item_url(alias, item_id)
            if not item_url:
                errors.append("Arkansas Digital Archives returned a record with an invalid collection or item identifier.")
                continue
            search_metadata = _metadata_values(item)
            if search_metadata.get("date") and not _in_date_range(search_metadata["date"], start_date, end_date):
                date_filtered += 1
                continue
            try:
                detail, api_body = _get_json(
                    f"{DIGITAL_ARCHIVE_API}/singleitem/collection/{alias}/id/{item_id}",
                    DIGITAL_ARCHIVE_HOST,
                    "Arkansas Digital Archives",
                )
            except (OSError, TimeoutError, ValueError) as error:
                errors.append(f"Could not read Arkansas archive item {item_url}: {error}")
                continue
            metadata = _metadata_values(detail)
            record_date = metadata.get("date", "")
            if not _in_date_range(record_date, start_date, end_date):
                date_filtered += 1
                continue
            title = metadata.get("title") or f"Arkansas Digital Archives item {item_id}"
            text = _text_field(detail, "text")
            description = metadata.get("descri", "")
            text_method = "archive-text" if text else "archive-catalog-text"
            text_label = "archive text" if text else "catalog text"
            metadata_text = " ".join(
                f"{key}: {value}" for key, value in metadata.items()
                if key != "rights" and value
            )
            text = text or description or metadata_text
            if not text:
                catalog_only += 1
                continue
            indexed_text = " ".join(
                value for value in (title, record_date, description, text) if value
            )
            item_metadata = {
                **metadata,
                "title": title,
                "date": record_date,
                "rights": metadata.get("rights", ""),
            }
            try:
                results.append(_write_capture(
                    evidence_dir, manifest_path, item_metadata, api_body, indexed_text[:6000], term,
                    "Arkansas State Archives Digital Archives", DIGITAL_ARCHIVE_HOST,
                    item_url, f"{DIGITAL_ARCHIVE_API}/singleitem/collection/{alias}/id/{item_id}",
                    "arkansas-digital-archives", text_method, text_label,
                ))
            except OSError as error:
                errors.append(f"Could not preserve Arkansas archive item {item_url}: {error}")
                break
            if delay:
                time.sleep(max(0.0, delay))
            if len(results) + catalog_only >= max_results:
                break
        if len(results) + catalog_only >= max_results or pages * RESULTS_PER_PAGE >= (total_matches or 0):
            break
        next_page += 1
        if delay:
            time.sleep(max(0.0, delay))
    return {
        "archive": "Arkansas State Archives Digital Archives",
        "query": term,
        "date_range": {"start": start_date or None, "end": end_date or None},
        "collection_scope": "All public Arkansas Digital Archives CONTENTdm collections.",
        "total_matches": total_matches,
        "pages_searched": pages,
        "pages_preserved": len(results),
        "catalog_only": catalog_only,
        "has_more": pages * RESULTS_PER_PAGE < (total_matches or 0),
        "result_limit": max_results,
        "matches": results,
        "errors": errors,
    }


def search_archives(
    query: str,
    evidence_dir: Path | str = "evidence",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 40,
) -> dict:
    """Search connected historical catalogs and preserve each source's results."""
    archives = [
        search_arkansas_digital_archives(query, evidence_dir, start_date, end_date, max_results),
        search_chronicling_america(query, evidence_dir, start_date, end_date, max_results),
    ]
    return {
        "query": str(query).strip(),
        "archives": archives,
        "pages_preserved": sum(item["pages_preserved"] for item in archives),
        "catalog_only": sum(item["catalog_only"] for item in archives),
        "has_more": any(item["has_more"] for item in archives),
        "matches": [match for item in archives for match in item["matches"]],
        "errors": [error for item in archives for error in item["errors"]],
    }
