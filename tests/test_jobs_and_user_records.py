import hashlib
import threading
import time

import jobs
import user_records as ur
from autopopulate import load_captures


def wait(job_id):
    for _ in range(200):
        job = jobs.get(job_id)
        if job["status"] in {"done", "failed"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_jobs_never_overlap_and_duplicates_are_not_queued():
    running, overlap = 0, []
    gate = threading.Event()

    def work():
        nonlocal running
        running += 1
        overlap.append(running)
        gate.wait(1)
        running -= 1
        return {"ok": True}

    first = jobs.submit("t1", work)
    again = jobs.submit("t1", work)
    other = jobs.submit("t2", work)
    assert again["id"] == first["id"] and other["id"] != first["id"]
    gate.set()
    assert wait(first["id"])["status"] == "done" and wait(other["id"])["status"] == "done"
    assert max(overlap) == 1


def test_failed_job_reports_error_and_does_not_kill_worker():
    def boom():
        raise RuntimeError("bad file")

    failed = wait(jobs.submit("boom", boom)["id"])
    assert failed["status"] == "failed" and "bad file" in failed["error"]
    assert wait(jobs.submit("after", lambda: {"x": 1})["id"])["result"] == {"x": 1}


def make_record(tmp_path, name, protection):
    evidence = tmp_path / "evidence"
    (evidence / "uploads").mkdir(parents=True, exist_ok=True)
    stored = evidence / "uploads" / name
    stored.write_bytes(b"Minutes of the council. Motion to approve $5,000.")
    return evidence, {"id": "r1", "stored_file": str(stored), "original_filename": name, "title": "Minutes", "protection": protection,
                      "sha256": hashlib.sha256(stored.read_bytes()).hexdigest(), "size_bytes": stored.stat().st_size}


def test_only_public_supported_files_are_indexed_and_pass_integrity_check(tmp_path):
    evidence, record = make_record(tmp_path, "m.txt", "public")
    assert ur.register_for_indexing(evidence, record)["indexed"]
    captures, rejected = load_captures(evidence)
    assert rejected == 0 and captures[0]["url"].startswith("local-record://") and captures[0]["content_type"] == "text/plain"

    evidence2, private = make_record(tmp_path / "b", "m.txt", "restricted")
    result = ur.register_for_indexing(evidence2, private)
    assert not result["indexed"] and not (evidence2 / ur.MANIFEST).exists()

    evidence3, image = make_record(tmp_path / "c", "book.xls", "public")
    assert not ur.register_for_indexing(evidence3, image)["indexed"]


def test_tampered_upload_is_rejected_by_pipeline(tmp_path):
    evidence, record = make_record(tmp_path, "m.txt", "public")
    ur.register_for_indexing(evidence, record)
    (evidence / "uploads" / "m.txt").write_bytes(b"changed")
    captures, rejected = load_captures(evidence)
    assert captures == [] and rejected == 1
