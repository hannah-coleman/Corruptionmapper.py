import investigation_guide as ig


def test_plan_targets_named_orgs_and_stays_on_public_sources():
    net = {"people": {"Adams": {"kind": "council member", "label": "Adams"}}, "awards": [{"x": 1}],
           "edges": [{"source": "A B", "target": "Acme LLC", "relation": "stated they represent", "evidence": []}]}
    tasks = ig.build_plan(net, [{"kind": "no-minutes", "status": "open"}])
    text = " ".join(t["task"] for t in tasks)
    assert "Acme LLC" in text and "Adams" in text
    assert all(t["rules_out"] and t["record"] for t in tasks)
    assert tasks == sorted(tasks, key=lambda t: t["priority"])
