import pytest

import layoffs as lo


def ev(**k):
    base = {"employer": "Acme", "date": "2026-03-31", "count": "30", "source": "s1", "positions": "Welder; Clerk"}
    base.update(k)
    return base


def build(tmp_path, events=(), postings=(), heads=()):
    path = tmp_path / "l.json"
    for e in events:
        lo.add(path, "events", e)
    for p in postings:
        lo.add(path, "postings", p)
    for h in heads:
        lo.add(path, "headcounts", h)
    return lo.report(path)["flags"]


def kinds(flags):
    return {f["kind"] for f in flags}


def test_requires_source_and_valid_values(tmp_path):
    path = tmp_path / "l.json"
    for bad in ({"source": ""}, {"date": "March"}, {"count": "-1"}, {"count": "x"}):
        with pytest.raises(ValueError):
            lo.add(path, "events", ev(**bad))


def test_short_notice_only_when_large_or_closure(tmp_path):
    assert "short-notice" in kinds(build(tmp_path, [ev(count="80", notice_date="2026-03-20")]))
    assert "short-notice" not in kinds(build(tmp_path / "b", [ev(count="80", notice_date="2026-01-01")]))
    assert "short-notice" not in kinds(build(tmp_path / "c", [ev(count="5", notice_date="2026-03-20")]))


def test_repeated_small_cuts_aggregate_within_90_days(tmp_path):
    flags = build(tmp_path, [ev(count="30"), ev(count="25", date="2026-05-01", source="s2")])
    assert "repeated-small-cuts" in kinds(flags)
    assert "repeated-small-cuts" not in kinds(build(tmp_path / "b", [ev(count="30"), ev(count="25", date="2026-12-01")]))


def test_reposted_position_and_headcount_mismatch(tmp_path):
    flags = build(tmp_path, [ev()], [{"employer": "ACME", "title": "welder", "date": "2026-05-01", "source": "p1"}],
                  [{"employer": "Acme", "period_end": "2026-01-31", "headcount": "200", "source": "h1"}, {"employer": "Acme", "period_end": "2026-06-30", "headcount": "120", "source": "h2"}])
    assert {"position-reposted", "headcount-mismatch"} <= kinds(flags)
    assert all(f["innocent_explanations"] and "does not show who was chosen" in f["caution"] for f in flags)
