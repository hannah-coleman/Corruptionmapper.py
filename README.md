# Corruption Mapper

*Experimental OSINT collection, structural auditing, and data governance framework.*

## Overview
Corruption Mapper is a modular Python and JavaScript application engineered for automated data ingestion, compliance auditing, and rigorous evidence tracking. 

## Project Status
🚧 **Active Development** — Core collectors and structural audit engines are functional. Expansion and refinement are ongoing.

## Core Components
* **Ingestion & Collectors:** Automated pipelines designed to gather and catalog public records and intelligence targets.
* **Audit Engines:** Validation workflows executing compliance checks and anomaly detection.
* **Structured Facts:** Dates, amounts, and vote tallies are extracted from preserved documents by deterministic rules, pinned to their exact passage and source hash, and confirmed or rejected by a named reviewer. Only confirmed facts feed the comparison and hypothesis engines. Your own uploads are restricted by default; run `python3 server.py --allow-protected` locally to review them.
* **Governance & Architecture:** Comprehensive structural frameworks (`APP_GOVERNANCE.md`, `CASEFILE_DESIGN.md`, etc.) defining data hygiene and boundary enforcement.

## Tech Stack
* **Backend:** Python 3, SQLite, Custom Audit Engines
* **Frontend:** JavaScript, HTML5, CSS3
* **Testing:** Pytest suite (`tests/`)

## Local Execution
```bash
git clone https://github.com/hannah-coleman/Corruptionmapper.py.git
cd Corruptionmapper.py
python3 -m pytest -q          # run the test suite
python3 server.py --port 8000 # serve the UI on 127.0.0.1 only
```

## Security Posture
The local server is designed to be safe by default. These controls are implemented and covered by tests (`tests/test_server_security.py`, `tests/test_web_security.py`):

* Binds to loopback only; rejects unexpected `Host` headers (DNS rebinding).
* State-changing requests must be same-origin and carry an `X-Signal-Ledger` header (cross-site request protection).
* Static files are served from an explicit allowlist only (no path traversal).
* Request bodies are size-limited; uploads are parsed without the deprecated `cgi` module.
* Web-triggered collection is limited to hosts in `targets.txt` / `source_registry.json`; the collector refuses non-public addresses and validates every redirect (SSRF protection).
* Restricted, counsel-protected, and unlabeled evidence is withheld from the API by default. Start with `--allow-protected` to expose it (operator decision).

Known limitations: no user authentication or per-user access control, no encryption at rest, and the audit log is tamper-evident but not externally anchored. Case data lives in `evidence/` and `backups/`, which are git-ignored and must never be committed.
