from backup import create_backup, verify_backup


def test_backup_preserves_and_verifies_every_file(tmp_path):
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "records.json").write_text('{"record": true}', encoding="utf-8")
    uploads = source / "uploads"
    uploads.mkdir()
    (uploads / "document.pdf").write_bytes(b"original record")

    created = create_backup(source, tmp_path / "backups")
    verified = verify_backup(created["archive"])

    assert created["files"] == 2
    assert verified["valid"] is True
    assert verified["files"] == 2