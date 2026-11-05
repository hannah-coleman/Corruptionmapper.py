import json

import lead_actions as la


FLAGS = [
    {"status": "open", "kind": "no-minutes", "message": "m", "link": {"detail": "2026-01-26 (#180)"}},
    {"status": "open", "kind": "vote-tally", "message": "t", "link": {"detail": "2026-02-23 (#178)"}},
    {"status": "open", "kind": "agenda-only", "message": "The agenda lists a property at 703 East Lake Street that the minutes never mention", "link": {"detail": "2026-06-08 (#185)"}},
    {"status": "resolved", "kind": "no-minutes", "message": "x", "link": {"detail": "2025-01-01"}},
]


def test_drafts_are_specific_neutral_and_skip_resolved_leads():
    drafts = la.request_drafts(FLAGS)
    text = " ".join(d["request_text"] for d in drafts)
    assert "2026-01-26" in text and "2026-02-23" in text and "703 East Lake Street" in text
    assert "2025-01-01" not in text
    assert all("25-19-101" in d["request_text"] and d["agency"] == la.CLERK for d in drafts)


def test_run_queues_drafts_once_and_writes_checklist(tmp_path, monkeypatch):
    (tmp_path / "discrepancy-flags.json").write_text(json.dumps(FLAGS), encoding="utf-8")
    monkeypatch.setattr(la.autopopulate, "load_captures", lambda _dir: ([], 0))
    first = la.run(tmp_path)
    second = la.run(tmp_path)
    assert first["draft_requests_added"] == 3 and second["draft_requests_added"] == 0
    assert all(r["status"] == "draft" for r in json.loads((tmp_path / "request-queue.json").read_text()))
    assert (tmp_path / "verification-checklist.md").exists()


def test_checklist_requires_identity_confirmation():
    net = {"edges": [{"source": "A B", "target": "Acme LLC", "relation": "stated they represent", "evidence": []}], "people": {}, "owners": {}}
    text = la.render_checklist(la.verification_checklist(net))
    assert "Acme LLC" in text and "Identity confirmed" in text and "sos-corp-search" in text
