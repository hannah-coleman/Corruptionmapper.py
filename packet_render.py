from __future__ import annotations

from html import escape


def _items(items: list[str]) -> str:
    return "".join(f"<li>{escape(str(item))}</li>" for item in items) or "<li>None recorded.</li>"


def _claims(claims: list[dict]) -> str:
    if not claims:
        return "<p>None recorded.</p>"
    return "".join(
        "<article><h3>{}</h3><p><strong>Review:</strong> {}</p><p><strong>Sources:</strong> {}</p>"
        "<p><strong>Alternative explanations:</strong></p><ul>{}</ul><p><strong>Next action:</strong> {}</p></article>".format(
            escape(str(claim.get("statement", ""))),
            escape(str(claim.get("review_status", "unreviewed"))),
            escape(", ".join(claim.get("source_ids", [])) or "None cited"),
            _items(claim.get("alternative_explanations", [])),
            escape(str(claim.get("next_test", "Not recorded"))),
        )
        for claim in claims
    )


def render_packet(packet: dict) -> str:
    source_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(str(source.get("id", ""))), escape(str(source.get("title", ""))),
            escape(str(source.get("url", ""))), escape(str(source.get("sha256", "Not recorded"))),
            escape("; ".join(item for item in [source.get("citation_page", ""), source.get("citation_section", ""), source.get("citation_excerpt", "")] if item) or "Not recorded"),
            escape("; ".join(item for item in [source.get("location_label", ""), f"{source.get('latitude')}, {source.get('longitude')}" if source.get("latitude") != "" and source.get("longitude") != "" else "", source.get("geographic_source_url", ""), source.get("imagery_captured_at", "")] if item) or "Not recorded"),
        ) for source in packet.get("source_index", [])
    ) or "<tr><td colspan=\"6\">No cited evidence records.</td></tr>"
    template = """<!doctype html><html><head><meta charset=\"utf-8\"><title>Signal Ledger Counsel Packet</title><style>
body{font:14px/1.5 Georgia,serif;color:#1d2926;margin:36px;max-width:900px}h1{margin-bottom:4px}h2{border-bottom:1px solid #bbb;padding-bottom:5px;margin-top:30px}h3{font-size:16px;margin-bottom:4px}article{border-left:3px solid #b28b35;padding-left:14px;margin:18px 0}.notice{background:#f4edd5;padding:14px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #bbb;padding:7px;text-align:left;vertical-align:top}@media print{body{margin:18mm}.notice{border:1px solid #bbb}}
</style></head><body><h1>Signal Ledger Counsel Review Packet</h1><p>Generated: {generated_at}</p><p class=\"notice\">{handling}</p><h2>Findings</h2>{findings}<h2>Open Questions and Working Hypotheses</h2>{open_questions}<h2>Contradicted Claims</h2>{contradicted}<h2>Source Index</h2><table><tr><th>Record ID</th><th>Title</th><th>URL</th><th>SHA-256</th><th>Exact citation</th><th>Geographic citation</th></tr>{sources}</table><h2>Limitations</h2><ul>{limitations}</ul></body></html>"""
    replacements = {
        "{generated_at}": escape(str(packet.get("generated_at", ""))),
        "{handling}": escape(str(packet.get("handling", ""))),
        "{findings}": _claims(packet.get("findings", [])),
        "{open_questions}": _claims(packet.get("open_questions", [])),
        "{contradicted}": _claims(packet.get("contradicted_claims", [])),
        "{sources}": source_rows,
        "{limitations}": _items(packet.get("limitations", [])),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template