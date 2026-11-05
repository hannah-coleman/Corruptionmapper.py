"""One command to refresh the living database: collect approved sources, index, compare, rebuild the report.

Run by hand (`python3 refresh.py`) or on a schedule, e.g. a daily launchd/cron job. Only approved hosts
are contacted, robots.txt is respected, and nothing logs in.
"""
from __future__ import annotations

import json

import autopopulate
import network_report
import open_data


def main() -> dict:
    import collector
    from pathlib import Path
    urls = collector.read_urls(Path("targets.txt"))
    collected = collector.collect_urls(urls, Path("evidence/raw"), delay=1.0)
    api = open_data.collect_all()
    summary = autopopulate.ingest()
    report = network_report.write_report()
    return {"pages": len(collected), "api": api, "ingest": summary, "report": str(report)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
