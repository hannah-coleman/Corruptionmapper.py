import json

import pytest

import run_local
from casefile_db import import_case


def test_new_case_is_empty_importable_and_never_overwrites(tmp_path):
    path = tmp_path / "evidence" / "casefile.json"
    run_local.new_case(path, "My Town review", ["My Town", "My County"])
    case = json.loads(path.read_text())
    assert case["title"] == "My Town review" and case["jurisdiction"] == ["My Town", "My County"]
    assert case["entities"] == [] and case["sources"] == [] and "Paragould" not in path.read_text()
    import_case(tmp_path / "db.sqlite", path)
