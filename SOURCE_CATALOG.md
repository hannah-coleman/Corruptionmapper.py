# Ultimate map source catalog

The mapper can be broad in **categories**, but every collection action remains narrow, lawful, and tied to an audit question. “Available online” does not automatically mean “licensed for bulk scraping” or “safe to republish.”

## Source families

### Government and public administration

- Paragould city pages: council, agendas, minutes, ordinances, budgets, procurement, permits, boards, and public notices.
- Greene County pages: Quorum Court, departments, budgets, bids, payments, assessor, treasurer, clerk, and sheriff materials.
- Arkansas state sources: Secretary of State business filings, courts, ethics, licensing, audits, legislative records, public safety, and agency oversight.
- Federal sources when relevant: PACER or court-publication alternatives, agency FOIA libraries, inspector-general reports, grants, contracts, campaign finance, and enforcement releases.

### Courts and legal process

- CourtConnect case metadata and permitted public filings.
- Orders, judgments, docket events, appeals, disciplinary matters, and public exhibits where allowed.
- Attorney filings are categorized as allegations or arguments; judicial findings and dispositions are separate categories.

### Money and entities

- Procurement, bid history, awards, amendments, invoices, payments, grants, reimbursements, and audit findings.
- LLC formation, officers, registered agents, amendments, assumed names, licenses, liens, property, and related public business records.
- Campaign finance, lobbying, political committees, gifts, disclosures, and public compensation where relevant and lawful.

### Communications and public reporting

- Official press releases, public meeting videos, agency social posts, public comments, publicly viewable complaints, journalism, and public videos.
- Public social material is captured only through permitted access, official APIs/exports, or individually selected public URLs. No private groups, fake identities, access bypasses, or indiscriminate bulk harvesting.

### Technical and scientific records

- Inspection reports, environmental measurements, equipment logs, laboratory reports, medical or pathology records only when lawfully obtained and necessary, and qualified expert analyses.
- Scientific data requires method, baseline, calibration, chain of custody, uncertainty, and qualified interpretation.

### DHS, CPS, and medical systems

- Public policies, contracts, budgets, audits, licensing, accreditation, training, aggregate statistics, public notices, and official responses.
- Personal child-welfare or medical records only through an authorized person, valid release, formal legal process, or counsel-directed request.
- Confidential case files, protected health information, child identifiers, school records, sealed material, and private portal content are restricted and excluded from broad collection. See `HEALTH_CHILD_SAFETY_WORKFLOW.md`.

## Source-level controls

Each source adapter must declare:

- owner or issuing body
- jurisdiction and record type
- public access method
- current terms or access restrictions
- robots/rate-limit behavior
- fields collected and sensitive fields excluded
- retention and republishing limits
- provenance and hash behavior
- error and access-denial handling
- human review requirement

An adapter stops on authentication, CAPTCHA, robots denial, rate limiting, sealed/restricted content, or unclear authority. It records the limitation instead of trying another route around it.

## Ultimate map depth model

- **Level 0 — Source:** URL, filing, video, record, post, or response.
- **Level 1 — Observation:** exact statement, amount, date, event, or document feature.
- **Level 2 — Event:** meeting, contract, payment, complaint, arrest, order, response, or procedural step.
- **Level 3 — Node:** person, agency, company, property, fund, court, policy, or group.
- **Level 4 — Relationship:** employed-by, awarded-to, paid-to, represented-by, voted-on, reported-by, responded-to, or shares-address-with.
- **Level 5 — Procedure:** required rule, authority, deadline, approval, notice, exception, and outcome.
- **Level 6 — Pattern:** repeated discrepancy or process deviation supported across independent events.
- **Level 7 — Review product:** chronology, source matrix, discrepancy report, records request, counsel packet, or public-interest report.

No higher level may be created without links back to lower-level evidence. A pattern prioritizes review; it does not establish intent or guilt.

## Completeness test

Before calling a map complete, ask:

1. What source category was not searched?
2. Which custodian may hold the missing record?
3. Which rule governs the event?
4. What source could disprove the current hypothesis?
5. Are the sources independent or copies of one another?
6. What information is sealed, exempt, privileged, private, or unsafe to collect?
7. What does counsel or a qualified expert need to review?
8. What lawful next action would reduce uncertainty most?
