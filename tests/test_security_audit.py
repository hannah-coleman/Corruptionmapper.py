from security_audit import assess_evidence_permissions, harden_evidence_permissions


def test_hardening_removes_group_and_world_access(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o755)
    record = evidence / "records.json"
    record.write_text("[]", encoding="utf-8")
    record.chmod(0o644)

    assert assess_evidence_permissions(evidence)["private"] is False
    result = harden_evidence_permissions(evidence)
    assert result["private"] is True
    assert stat_mode(record) == 0o600


def stat_mode(path):
    import stat
    return stat.S_IMODE(path.stat().st_mode)