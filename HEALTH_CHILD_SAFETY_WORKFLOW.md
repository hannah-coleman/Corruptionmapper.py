# DHS, CPS, and medical-system workflow

These sources may be relevant to a defense or retaliation chronology, but they must never become a private-data harvesting lane. The mapper should minimize sensitive data and record only what is necessary for the defined legal question.

## Possible lawful evidence categories

- Public agency policies, manuals, contracts, budgets, audits, accreditation findings, inspection reports, training materials, and aggregate statistics.
- Public meeting materials, administrative decisions, notices, hearing dates, redacted orders, and official responses where lawfully public.
- A person's own records, or a child's records, only through the legally authorized person, a valid release, formal process, or counsel-directed request.
- Medical records only when lawfully obtained and necessary, with provider, patient, or counsel guidance on authorization, minimum necessary scope, and secure handling.
- Public licensing, disciplinary, compliance, and enforcement records where the issuing authority makes them public.

## Restricted material

Do not scrape or publish confidential CPS case files, child-identifying information, medical records, protected health information, school records, foster-care information, sealed proceedings, private portal content, or information about unrelated families. Do not infer abuse, disability, diagnosis, incapacity, or medical causation from a report, symptom, referral, or timing alone.

A subpoena, discovery request, protective order, court authorization, medical-record authorization, or other formal process belongs with counsel. Public-records laws do not automatically override confidentiality statutes or court orders, and federal FOIA is not a general route to private medical or child-welfare files.

## Minimum casefile fields

Use a restricted-access source class and record:

- issuing system or custodian, record category, and lawful access basis
- date range, event date, and procedural posture
- redaction or confidentiality status
- exact proposition needed for the audit, not the entire sensitive record by default
- source location, capture time, hash or chain of custody where permitted
- authorized viewers, retention period, and deletion or return requirement
- counsel review status and whether a redacted summary is sufficient

## Audit questions

- What policy, notice, deadline, consent, accommodation, or procedural safeguard applies?
- What was documented, by whom, and when?
- Was the record created contemporaneously or later summarized?
- What did the record actually establish, and what did it not establish?
- Were corrections, addenda, conflicting accounts, and exculpatory records preserved?
- Is the apparent inconsistency clerical, procedural, clinical, or unresolved?
- What is the least intrusive lawful record or expert review that would reduce uncertainty?

## Safety and privacy gate

Before importing any sensitive item, confirm with counsel that it is necessary and lawfully obtained. Store it separately from the public-source graph, encrypt it, minimize identifiers, log access, and show only a redacted description in ordinary graph views. Any immediate threat to a child or vulnerable person should be handled through emergency services, a qualified advocate, and counsel rather than through public investigation.
