from foia_plan import ARKANSAS_FOIA, COURT_RULE, build_plan

REGISTRY = [
    {"id": "city", "label": "City of Testville", "category": "government", "jurisdiction": "local", "access": "public-search", "request_route": "City clerk", "status": "verify-official-url", "hosts": ["city.example.gov"]},
    {"id": "court", "label": "Test Courts", "category": "judicial", "jurisdiction": "state", "access": "public-search", "request_route": "Clerk", "status": "ok", "hosts": ["courts.example.gov"]},
    {"id": "sensitive", "label": "Sensitive", "category": "restricted", "jurisdiction": "mixed", "access": "restricted", "request_route": "Counsel", "status": "do-not-bulk-collect"},
]


def test_restricted_sources_are_never_suggested():
    plan = build_plan(REGISTRY, [], [])
    assert {item["agency_id"] for item in plan} == {"city", "court"}


def test_evidence_indicated_suggestions_cite_the_captured_page():
    docs = [{"url": "https://city.example.gov/agenda", "title": "Agenda", "content": "Council approved a contract amendment for paving."},
            {"url": "https://other.example.org/", "title": "Other", "content": "contract everywhere"}]
    plan = build_plan(REGISTRY, docs, [])
    city = next(item for item in plan if item["agency_id"] == "city")
    indicated = [s for s in city["suggestions"] if s["basis"] == "evidence-indicated"]
    assert [s["document_type"] for s in indicated] == ["contract and amendment files"]
    assert indicated[0]["evidence"][0]["url"] == "https://city.example.gov/agenda"
    assert "contract amendment" in indicated[0]["evidence"][0]["excerpt"]
    assert plan[0]["agency_id"] == "city"  # agencies with evidence-driven leads sort first
    assert city["law"] == ARKANSAS_FOIA


def test_courts_use_court_rules_and_drafts_are_neutral():
    plan = build_plan(REGISTRY, [], [], time_range="January 1, 2024 to present")
    court = next(item for item in plan if item["agency_id"] == "court")
    assert court["law"] == COURT_RULE
    draft = court["suggestions"][0]["draft"]["request_text"]
    assert "January 1, 2024 to present" in draft
    assert "segregable" in draft


def test_existing_requests_are_flagged():
    existing = [{"agency": "City of Testville", "description": "Please send payment and vendor registers for 2024"}]
    city = next(item for item in build_plan(REGISTRY, [], existing) if item["agency_id"] == "city")
    flagged = {s["document_type"]: s["already_requested"] for s in city["suggestions"]}
    assert flagged["payment and vendor registers"] is True
    assert flagged["meeting agendas, minutes, attachments, and recordings"] is False


def test_boilerplate_and_non_substantive_pages_are_not_signals():
    nav = [{"url": f"https://city.example.gov/page{i}", "title": "p", "content": "Home | Court | Contact"} for i in range(6)]
    nav.append({"url": "https://city.example.gov/MyAccount/Login", "title": "login", "content": "contract fund payment meeting permit"})
    city = next(item for item in build_plan(REGISTRY, nav, []) if item["agency_id"] == "city")
    assert not [s for s in city["suggestions"] if s["basis"] == "evidence-indicated"]
    mixed = nav + [{"url": "https://city.example.gov/bids/7", "title": "Bid 7", "content": "Bid award and payment schedule"}]
    city = next(item for item in build_plan(REGISTRY, mixed, []) if item["agency_id"] == "city")
    indicated = [s for s in city["suggestions"] if s["basis"] == "evidence-indicated"]
    assert [s["document_type"] for s in indicated] == ["payment and procurement records"]
