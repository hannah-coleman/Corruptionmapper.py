"""One background worker for slow evidence jobs (OCR, indexing, fact extraction, comparison).

The jobs read and rewrite the same derived files, so they must never overlap. A single worker thread
plus one process-wide lock serializes them, whether a job is started in the background or run directly
inside a request. A job that is already queued or running is returned instead of being queued again.
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

PIPELINE_LOCK = threading.RLock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evidence-job")
_jobs: dict[str, dict] = {}
_guard = threading.Lock()
MAX_REMEMBERED = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def submit(name: str, work: Callable[[], dict]) -> dict:
    with _guard:
        for job in _jobs.values():
            if job["name"] == name and job["status"] in {"queued", "running"}:
                return dict(job)
        job = {"id": uuid4().hex[:12], "name": name, "status": "queued", "queued_at": _now(), "result": None, "error": ""}
        _jobs[job["id"]] = job
        while len(_jobs) > MAX_REMEMBERED:
            oldest = next(key for key, value in _jobs.items() if value["status"] in {"done", "failed"})
            del _jobs[oldest]

    def run() -> None:
        job["status"], job["started_at"] = "running", _now()
        try:
            with PIPELINE_LOCK:
                job["result"] = work()
            job["status"] = "done"
        except Exception as error:  # reported to the user; the traceback goes to the server log
            traceback.print_exc()
            job["status"], job["error"] = "failed", f"{type(error).__name__}: {error}"
        job["finished_at"] = _now()

    _executor.submit(run)
    return dict(job)


def get(job_id: str) -> dict | None:
    with _guard:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def run_pipeline(evidence_dir: Path | str = "evidence") -> dict:
    """Index, extract facts and re-run comparisons; serialized with every other job."""
    from audit_log import append_entry
    from autopopulate import ingest

    evidence_dir = Path(evidence_dir)
    with PIPELINE_LOCK:
        summary = ingest(evidence_dir)
        append_entry(evidence_dir / "audit.jsonl", "autopopulate-run", details={key: summary[key] for key in ("captures", "indexed", "records_added", "facts_proposed")})
        return summary
