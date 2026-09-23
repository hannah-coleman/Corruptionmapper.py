# Signal Ledger category architecture

## One system, protected compartments

Use one casefile so timelines and relationships can be connected, but separate the data by sensitivity and purpose:

- **Public evidence graph:** public records, official pages, public court materials, public business filings, public statements, and permitted public social sources.
- **Restricted evidence vault:** personal medical, child-welfare, disability, school, home-address, witness-safety, and counsel-protected material. Raw files are excluded from ordinary graph views.
- **Analytic layer:** observations, comparisons, timelines, discrepancies, hypotheses, alternative explanations, and Logos reasoning entries.
- **Handoff layer:** neutral packets routed to counsel, records custodians, qualified experts, safety support, or appropriate oversight.

The vault can connect to the public graph only through a redacted reference such as `restricted-event-014`, with the lawful access basis, reviewer, and exact proposition needed. Do not expose the underlying record by default.

## Required lanes

Every source and event gets one primary lane and may have cross-lane links:

1. **Business and finance:** LLCs, officers, agents, contracts, bids, payments, grants, property, liens, licenses, campaign finance, lobbying, and disclosures.
2. **Medical and health:** authorized clinical records, pathology, testing, accommodations, public health policy, inspections, and expert review.
3. **Child welfare and family safety:** public policy, notices, hearings, authorized records, mandated-process documentation, and safety chronology.
4. **Law enforcement and corrections:** policies, dispatch, incidents, complaints, discipline, use of force, jail records, body-camera material where releasable, and official responses.
5. **Legal and judicial:** CourtConnect, dockets, pleadings, orders, judgments, appeals, disciplinary matters, and procedural posture.
6. **Political and civic:** elections, campaign finance, lobbying, meetings, votes, appointments, ethics disclosures, public statements, and constituent processes.
7. **Government and administration:** procurement, budgets, audits, grants, permits, licensing, records retention, notices, and agency procedures.
8. **Communications and media:** official releases, public social posts, public videos, journalism, complaints, corrections, and source independence.
9. **Scientific and technical:** environmental measurements, equipment logs, laboratory material, digital forensics, pathology, and qualified expert opinions.
10. **Timeline and response:** events, deadlines, notices, complaints, institutional actions, delays, denials, corrections, escalation, and silence.
11. **Oversight and remedy:** inspector, ethics, accreditation, licensing, ombuds, administrative review, appeals, civil remedies, and counsel decisions.

## How lanes connect

Cross-lane links must use a defined relation and source:

- `person-held-role-at-time`
- `entity-awarded-contract`
- `payment-supported-by-record`
- `agency-required-procedure`
- `court-record-refers-to-event`
- `complaint-triggered-response`
- `medical-or-welfare-record-documents-event`
- `public-statement-responds-to-record`
- `oversight-review-addresses-process`
- `same-event-different-account`

Each link is labeled `direct`, `inferred`, or `unresolved`. A cross-lane connection is not evidence of wrongdoing by itself.

## Effectiveness features

- **Coverage dashboard:** categories searched, custodians contacted, records pending, and blind spots.
- **Chronology engine:** local time, UTC, source version, deadline, knowledge point, response, and appeal status.
- **Procedure comparator:** required step versus observed step, with rule version and exception handling.
- **Discrepancy workspace:** exact passages side by side, classification, alternative explanations, and disposition.
- **Independence checker:** identifies copied reporting and shared underlying sources.
- **Identity resolver:** prevents merging people or companies with similar names and preserves uncertainty.
- **Negative-evidence register:** records searches that found nothing, scope, date, and limitations.
- **Request tracker:** Arkansas public-records requests, federal FOIA requests, clerk processes, fees, denials, and deadlines kept distinct.
- **Counsel packet builder:** neutral chronology, source index, unresolved issues, exculpatory material, and redaction controls.
- **Safety controls:** least privilege, encryption, access log, secure backup, retention schedule, and emergency escalation guidance.
- **Reproducibility:** every analytic result explains its inputs, rule, version, and reviewer.

## Operating principle

Be a calm, lawful accountability researcher. The objective is clarity and remedy, not intimidation or retaliation. “Malicious compliance” is not a software requirement: follow the law, platform rules, court orders, privacy duties, and counsel's instructions exactly, and document barriers when they occur.
