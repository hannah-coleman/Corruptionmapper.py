import pytest

import property_map as pm

ROW = {"name": "100 Main St", "kind": "property", "owner": "Acme LLC", "agent": "Registered Agents Inc", "source": "evidence/raw/a.bin", "lat": "36.05", "lon": "-90.50"}


def test_place_requires_source_and_valid_coordinates(tmp_path):
    path = tmp_path / "places.json"
    for bad in ({"source": ""}, {"name": ""}, {"kind": "enemy"}, {"lat": "abc"}, {"lat": "99"}, {"lon": ""}):
        with pytest.raises(ValueError):
            pm.add_place(path, {**ROW, **bad})
    assert pm.add_place(path, ROW)["id"]


def test_links_come_only_from_shared_filed_values_and_carry_sources(tmp_path):
    path = tmp_path / "places.json"
    pm.add_place(path, ROW)
    pm.add_place(path, {**ROW, "name": "Acme Store", "kind": "business", "owner": " acme  llc ", "agent": "Someone Else", "lat": "", "lon": "", "source": "sos.pdf"})
    pm.add_place(path, {**ROW, "name": "Unrelated", "owner": "Other", "agent": "Nobody"})
    data = pm.build_map(path)
    assert len(data["links"]) == 1 and data["links"][0]["relation"] == "same owner of record"
    assert data["links"][0]["sources"] == ["evidence/raw/a.bin", "sos.pdf"] and "Confirm" in data["links"][0]["caution"]
    assert len(data["unplaced"]) == 1


def test_csv_import_reports_row_errors_and_keeps_good_rows(tmp_path):
    path = tmp_path / "places.json"
    text = "name,kind,source,lat,lon\nA,church,s1,36.1,-90.4\nB,church,,36.1,-90.4\n"
    result = pm.import_csv(path, text)
    assert result["added"] == 1 and "Row 3" in result["errors"][0]
