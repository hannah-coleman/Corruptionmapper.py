# Signal Ledger governance and reliability

## Operating posture

Signal Ledger is a research, preservation, analysis, and routing system. It is not law enforcement, a court, a medical diagnostic system, a public blacklist, or an automated accusation engine.

## Data lifecycle

1. **Intake:** explicitly selected source or authorized user record enters with provenance and access basis.
2. **Preservation:** original bytes, exact text, hash, timestamp, and collection limitations are retained where lawful.
3. **Normalization:** structured fields are added without replacing the original.
4. **Analysis:** rules produce explainable flags and links.
5. **Human review:** a reviewer records disposition, counterevidence, alternative explanation, and next action.
6. **Handoff:** a neutral packet goes only to the appropriate desk.
7. **Closure:** the issue is supported, contradicted, insufficient, duplicate, out of scope, or counsel-directed, with the reason preserved.

## Required controls

- Schema version on every export.
- Immutable source and audit-log entries; corrections are append-only revisions.
- Least-privilege roles: owner, researcher, reviewer, counsel, expert, and export-only.
- Separate public, restricted, and counsel-protected storage.
- Encryption at rest and in transit when deployed beyond a local machine.
- Access log for every restricted item and export.
- Retention and deletion schedule reviewed by counsel.
- Backup and restore test before real sensitive material is added.
- Provenance warning when a source is unavailable, changed, derivative, or incomplete.
- Suspected protected or leaked material is stopped and routed through the quarantine protocol; it is not imported into the casefile.
- Human confirmation before external contact, filing, escalation, or publication.

## Quality metrics

Track these as health measures, not performance theater:

- percentage of records with complete provenance
- percentage of material claims with independent corroboration attempted
- number of unresolved contradictions
- percentage of flags with human disposition
- false-positive and retraction rate
- percentage of restricted records with current access authorization
- request response and appeal deadlines at risk
- source categories and custodians not yet searched
- percentage of exports that reproduce from their recorded inputs

## Human review form

Every material flag should answer:

- What is the neutral issue?
- What exact evidence triggered it?
- What rule, baseline, or expected process is relevant?
- What does the evidence establish?
- What does it not establish?
- What supports it and what weakens it?
- What innocent explanations fit?
- What is the least intrusive next lawful test?
- Which desk owns the next action?
- What deadline, safety, privacy, privilege, or publication risk exists?
- Who reviewed it, when, and with what disposition?

## Export classes

- **Working export:** includes unresolved leads and internal notes; never automatically public.
- **Counsel packet:** includes source index, chronology, limitations, contradictions, and restricted-material references controlled by counsel.
- **Oversight packet:** neutral, narrowly scoped, redacted, and directed to the correct jurisdiction.
- **Public report:** only after legal and privacy review, with claims no broader than sources and a clear corrections path.

## Failure behavior

When access is denied, a parser fails, a source changes, a hash differs, a record is sealed, or identity resolution is uncertain, the system must stop or mark the limitation. It must never silently substitute, guess, merge, or escalate.
