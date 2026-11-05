import backup


def test_no_backup_yet(tmp_path):
    result = backup.latest_backup_status(tmp_path / "none")
    assert result["valid"] is False and "No backup" in result["issues"][0]


def test_latest_backup_is_verified_and_damage_is_reported(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_text("one")
    created = backup.create_backup(source, tmp_path / "b")
    status = backup.latest_backup_status(tmp_path / "b")
    assert status["valid"] and status["files"] == 1 and status["archive"] == created["archive"]
    with open(created["archive"], "r+b") as handle:
        handle.seek(40)
        handle.write(b"\xff\xff\xff\xff")
    assert backup.latest_backup_status(tmp_path / "b")["valid"] is False
