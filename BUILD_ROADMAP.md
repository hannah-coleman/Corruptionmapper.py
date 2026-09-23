# Signal Ledger build roadmap

## Phase 1: defensible casefile

- Persistent local database for sources, observations, entities, events, rules, requests, discrepancies, responses, and Logos entries.
- Import normalized JSON and collector manifests.
- Evidence lanes, confidence, review status, exculpatory evidence, and audit log.
- Micro-to-macro graph with explainable edges.
- Export a counsel-ready evidence index and chronology.

## Phase 2: discrepancy and procedure engine

- Compare dates, amounts, names, versions, vote counts, approvals, and required process steps.
- Show exact source passages side by side.
- Add rule-version tracking and jurisdiction-specific request templates.
- Require a human review note before closing a flag.
- Keep false-positive and innocent-explanation outcomes visible.

## Phase 3: lawful source adapters

Add one adapter at a time, with terms and access review:

1. Official city and county pages, minutes, agendas, procurement, budgets, and payments.
2. Arkansas Secretary of State business records and relevant state filings.
3. Public court dockets and filings where permitted.
4. Public oversight, licensing, ethics, audit, and accreditation records.
5. Public social posts and videos through permitted access or official APIs/exports.

Adapters should collect only defined fields, rate-limit, cache responsibly, preserve provenance, and stop when access is restricted. No broad indiscriminate crawling.

CourtConnect gets its own review gate: index only the case and docket information needed for the defined question, distinguish filings from judicial findings, track disposition and appeals, and never bypass access or copy sealed/restricted material. See `COURT_CONNECT_WORKFLOW.md`.

## Phase 4: review and reporting

- Discrepancy queue sorted by materiality, source quality, deadline, and safety risk.
- Timeline and relationship views linked to source passages.
- Request tracker for Arkansas records requests and federal FOIA separately.
- Counsel review workspace with redaction and export controls.
- Report builder that includes limitations, counterevidence, unresolved items, and source index.

## Phase 5: mobile companion

The mobile app should capture and review, not perform uncontrolled collection:

- Secure local incident notes and timestamps.
- Camera/import with hash and provenance metadata.
- Offline access to the case chronology and request status.
- Safe-share/export to counsel.
- Permission minimization, encryption, screen-lock support, and no background location by default.
- Clear separation between personal safety notes and material intended for public release.

## Product principles

- Human review before escalation.
- Evidence before interpretation.
- Narrow claims before broad patterns.
- Primary sources before commentary.
- Exculpatory information is first-class evidence.
- Every automated flag must explain itself.
- No automated accusation, diagnosis, doxxing, or legal conclusion.

## Government-grade completion baseline

The project is not complete until the system can credibly support lawful accountability without becoming a surveillance, punishment, or public-shaming engine.

### Must-have core capabilities

- Provenance ledger for every imported fact, source, file, and claim.
- Public, restricted, and counsel-protected evidence separation.
- Evidence ladder: fact, corroborated fact, inference, allegation, contradiction, and unresolved lead.
- Counterevidence and exculpatory evidence tracking as first-class evidence, not afterthoughts.
- Human review workflow with reviewer identity, timestamp, rationale, and disposition.
- Risk and harm classification with privacy, child-safety, and retaliation risk controls.
- Least-intrusive intervention planner tied to real legal or oversight pathways.
- Audit log, appeal path, and export controls for every material report.

### High-impact capability gaps to close next

- Legal relevance engine that links observations to statutes, policies, procedures, and known standards.
- Review queue sorted by materiality, source quality, deadline, and safety risk.
- Counsel-ready packet with chronology, limitations, contradictions, and source index.
- Oversight export with redactions and narrow scope.
- Sensitive-subject protections for minors, victims, witnesses, and vulnerable persons.
- Search and graph views that exclude protected material by default.

### Explicit scope boundaries

The app should not automate punishment, detention, sentencing, public guilt declarations, or mass public exposure. It should support lawful investigation, evidence integrity, intervention planning, and oversight review.

### Readiness standard

The system is ready for serious government-facing review when it can demonstrate all of the following:

- every flag is traceable to source, rule, and review status
- every contradiction is visible and explained
- every restricted item is isolated and access-controlled
- every export is scoped to a lawful purpose
- every finding is human-reviewed before escalation
- every vulnerable subject is protected from ordinary graph exposure
- every report distinguishes proof, inference, and uncertainty
