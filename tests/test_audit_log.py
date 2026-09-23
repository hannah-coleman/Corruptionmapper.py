from audit_log import append_entry, verify_log


def test_hash_chained_log_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    append_entry(path, "evidence-created", "record-1")
    append_entry(path, "claim-created", "claim-1")
    assert verify_log(path)["valid"] is True

    path.write_text(path.read_text(encoding="utf-8").replace("claim-created", "claim-altered"), encoding="utf-8")
    assert verify_log(path)["valid"] is False