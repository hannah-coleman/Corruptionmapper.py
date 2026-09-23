from packet_render import render_packet


def test_printable_packet_escapes_claim_text_and_renders_required_sections():
    html = render_packet({
        "generated_at": "2026-01-01", "handling": "Internal only",
        "findings": [], "contradicted_claims": [],
        "open_questions": [{"statement": "Is <script>safe?</script>", "review_status": "unreviewed", "source_ids": [], "alternative_explanations": [], "next_test": "Check record"}],
        "source_index": [], "limitations": ["No conclusion."],
    })

    assert "&lt;script&gt;safe?&lt;/script&gt;" in html
    assert "Open Questions and Working Hypotheses" in html
    assert "Source Index" in html


def test_printable_packet_renders_escaped_exact_citation():
    html = render_packet({"generated_at": "", "handling": "", "findings": [], "open_questions": [], "contradicted_claims": [], "limitations": [], "source_index": [{"id": "e1", "title": "Minutes", "url": "", "citation_page": "4", "citation_section": "Item 7", "citation_excerpt": "<quoted> text"}]})

    assert "Exact citation" in html
    assert "4; Item 7; &lt;quoted&gt; text" in html


def test_printable_packet_renders_geographic_citation():
    html = render_packet({"generated_at": "", "handling": "", "findings": [], "open_questions": [], "contradicted_claims": [], "limitations": [], "source_index": [{"id": "e1", "title": "Map", "url": "", "location_label": "Public parcel", "latitude": 36.05, "longitude": -90.49, "geographic_source_url": "https://example.gov/gis"}]})

    assert "Geographic citation" in html
    assert "Public parcel; 36.05, -90.49; https://example.gov/gis" in html