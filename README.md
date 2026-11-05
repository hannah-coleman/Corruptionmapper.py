# Corruption Mapper

*Experimental OSINT collection, structural auditing, and data governance framework.*

## Overview

Corruption Mapper is a modular Python and JavaScript application engineered for automated data ingestion, compliance auditing, and rigorous evidence tracking.

## Project Status

🚧 **Active Development** — Core collectors and structural audit engines are functional. Expansion and refinement are ongoing.

This is a research workspace, not a law-enforcement system or a finding that wrongdoing occurred. Treat leads as unverified, preserve source material, document contrary evidence and alternative explanations, and have consequential conclusions reviewed by qualified people.

## Core Components

* **Ingestion & Collectors:** Automated pipelines designed to gather and catalog public records and intelligence targets.
* **Audit Engines:** Validation workflows executing compliance checks and anomaly detection.
* **Question-driven research:** Lead reports suggest follow-up questions from open record discrepancies. “Ask the records” searches captured public pages and lets you save a question to the research ledger; matches are evidence leads, not generated answers. Historical Archive Discovery searches the public Arkansas State Archives Digital Archives CONTENTdm collections and digitized U.S. newspaper OCR in the Library of Congress Chronicling America API, preserves matching text with provenance, then indexes it for cross-reference. This does not search every archive; other catalogs and inaccessible collections are listed as coverage gaps.
* **Structured Facts:** Dates, amounts, and vote tallies are extracted from preserved documents by deterministic rules, pinned to their exact passage and source hash, and confirmed or rejected by a named reviewer. Only confirmed facts feed the comparison and hypothesis engines. Your own uploads are restricted by default; run `python3 server.py --allow-protected` locally to review them.
* **Governance & Architecture:** Comprehensive structural frameworks (early planning notes, kept in `docs/early-design/` and possibly out of date) defining data hygiene and boundary enforcement.

## Tech Stack

* **Backend:** Python 3, SQLite, Custom Audit Engines
* **Frontend:** JavaScript, HTML5, CSS3
* **Testing:** Pytest suite (`tests/`)

## Responsible use

- **Keep case data local.** Names, evidence, notes and maps live in `evidence/` and `.private-terms.txt`, which are git-ignored. Run `python3 scripts/check_no_case_data.py --install` to add a pre-commit check that blocks case files and any term you list in `.private-terms.txt`. Never publish case data to a public repository.
- **Leads, not findings.** The app reports where public records disagree. It does not determine intent or wrongdoing, and it does not infer family, religious, or social relationships.
- **Use lawful sources only.** Follow each source's terms, robots rules and Arkansas law. Do not bypass access controls. Use records requests for anything not public.
- **Be careful with people.** Private individuals deserve privacy; focus on official acts and public filings. Check names against a second identifier before linking anyone. Get legal advice before sharing results, especially if you are a party to a legal matter.
- **No warranty.** This software is provided as described in the [LICENSE](LICENSE) and is not legal advice.

## Local Execution

Keep real case data on your own computer for now. This application has no user sign-in, encryption at rest, or per-user access controls; do not deploy it to a public host or expose its local server to your network.

```bash
git clone https://github.com/hannah-coleman/Corruptionmapper.py.git
cd Corruptionmapper.py
python3 -m pip install -r requirements.txt
python3 run_local.py --new-case "My case title" --places "Town, County, State"   # first run only: creates an empty evidence/casefile.json
python3 run_local.py            # every later run: uses evidence/casefile.json and a local SQLite index
```

Each person runs their own copy with their own `evidence/` folder; nothing is shared between copies.

Open the printed `http://127.0.0.1:...` address in your browser. Stop the app with Ctrl-C. The server binds to loopback only. The launcher finds project assets and default data paths even if started from another directory.

By default, restricted, counsel-protected, and unlabeled records are hidden. To review them in your local session, stop the app and explicitly restart:

```bash
python3 run_local.py --allow-protected
```

Anyone or any software running under your computer account may be able to access local files or the loopback app; this option is not a substitute for authentication. Keep the casefile and evidence directory private and backed up. Do not put originals in Git, email, or a public demo.

Turn open leads into action with `python3 lead_actions.py`. It queues neutral draft records requests (never sent automatically) in `evidence/requests.json` and writes `evidence/verification-checklist.md` for sources that block automated access, such as the Secretary of State business search. Search those by hand, save the result with *Preserve local file*, and confirm identity before linking any name.

Verify each lead against the original page with `POST /api/discrepancies/<id>/verify` (method, result, reviewer, note, page). A lead counts as verified only if a person recorded the check, and the check is voided if the extracted text later changes. `python3 lead_packet.py` writes `evidence/lead-packet.md` and `.json`: leads grouped by verification level, each with source URL, capture date, SHA-256 (re-hashed at build time), the quoted passage, innocent explanations and next step, plus the request log and an up-front statement of limits. Leads not marked public are left out.

Open `http://127.0.0.1:8000/start.html` for the guided home screen: status, the lead verification panel, the place map (`/map.html`) and the layoff log (`/layoffs.html`). The layoff log checks timing and count patterns (short notice, repeated small cuts, reposted positions, headcount vs. logged layoffs) from records you enter; it cannot show who was chosen or why. Layoff and map data are stored in git-ignored files under `evidence/`.

**Adding your own records.** On the home screen, *Add your own record* saves a file with a SHA-256 and timestamp. If you mark it a public record (PDF, HTML or plain text), it is indexed and compared with everything else; anything not marked public is preserved but never indexed or compared. Indexing and comparison run in one background worker (`jobs.py`) so long runs never block the page or overlap; the home screen shows progress. Scanned PDFs and images (png, jpg, tiff) are read by local OCR on macOS (Apple Vision; nothing leaves the computer); on other systems they need to be transcribed by hand. OCR text is marked as such and every lead built from it stays unverified until you check it against the page image. Word (.docx) and Excel (.xlsx) files are read directly (formulas are not evaluated; older .doc/.xls must be saved as the newer format).

For development:

```bash
python3 -m pytest -q          # run the test suite
```

## Security Posture

The local server is designed to be safe by default. These controls are implemented and covered by tests (`tests/test_server_security.py`, `tests/test_web_security.py`):

* Binds to loopback only; rejects unexpected `Host` headers (DNS rebinding).
* State-changing requests must be same-origin and carry an `X-Signal-Ledger` header (cross-site request protection).
* Static files are served from an explicit allowlist only (no path traversal).
* Request bodies are size-limited; uploads are parsed without the deprecated `cgi` module.
* Web-triggered collection is limited to hosts in `targets.txt` / `source_registry.json`; the collector refuses non-public addresses and validates every redirect (SSRF protection).
* Restricted, counsel-protected, and unlabeled evidence is withheld from the API by default. The local launcher requires `--allow-protected` to expose it.

Known limitations: no user authentication or per-user access control, no encryption at rest, and the audit log is tamper-evident but not externally anchored. Case data lives in `evidence/` and `backups/`, which are git-ignored and must never be committed. “Government-grade” certification or compliance is not claimed.


## Case review (neutral record comparison)

`/cases.html` lets you enter the records for a case (reports, booking records, policies or SOPs, news or public statements, and a person's recollection), each with its source. It shows a timeline, labelled values that differ between records (times, charge, statute, location, people present), each policy requirement beside the record passages that use the same terms, and wording features (indirect phrasing, actions with no named actor).

- It never says which record is accurate, why records differ, or whether anyone broke a rule or law. Recollections are shown as given, not as established. Policies are shown beside records for a reviewer or attorney to weigh.
- Reports replace private individuals with codes (Person-A) unless they are marked as having agreed to be named. People acting in an official role keep their names. The screen view on your own computer is not redacted; exports are. Check any export before sharing it.
- The cross-case view lists officials who appear in two or more entered cases. Counts come from self-selected entries, are not rates, and say nothing about conduct.
- "Ask an agency for its policies" queues an unsent FOIA draft in the request queue.
- Entries are stored in `evidence/case-review.json`, which is git-ignored and blocked by the commit guard.
- This is a records-organizing tool, not legal advice. If it is used for other people's cases, get a lawyer to review your client terms, confidentiality and data handling first.
