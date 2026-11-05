import subprocess

import pytest

SCRIPT = "scripts/check_no_case_data.py"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("guard", Path(__file__).resolve().parent.parent / SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    run("init", "-q")
    return guard, tmp_path, run


def test_blocks_case_files_and_private_terms_but_allows_normal_code(repo):
    guard, root, run = repo
    (root / ".private-terms.txt").write_text("# names\nJane Doe\n")
    (root / "evidence").mkdir()
    (root / "evidence" / "notes.txt").write_text("x")
    (root / "claims.json").write_text("[]")
    (root / "app.py").write_text("# thanks to jane doe\n")
    (root / "ok.py").write_text("print(1)\n")
    run("add", "-f", "evidence/notes.txt", "claims.json", "app.py", "ok.py")
    found = guard.problems()
    assert any("evidence/notes.txt" in f for f in found)
    assert any("claims.json" in f for f in found)
    assert any("app.py" in f and "private-terms" in f for f in found)
    assert not any("ok.py" in f for f in found)
