# Sensitive-data handling policy

## Absolute boundary

Signal Ledger does not collect, download, store, index, analyze, transmit, or publish leaked, hacked, stolen, or improperly disclosed child-welfare, medical, disability, school, foster-care, genetic, or other protected records. A file being publicly reachable or offered to the researcher does not establish lawful possession or lawful use.

No software can guarantee zero legal liability. Before handling sensitive material, obtain advice from counsel familiar with the applicable jurisdiction, privacy rules, protective orders, and the specific record type.

## Safe incident response

If someone sends or points to sensitive material:

1. Do not forward, download, copy, screenshot, open additional links, or add it to the case database.
2. Record only minimal routing metadata: date/time, sender or source category, URL if necessary for counsel to locate it, and a neutral description such as `possible protected disclosure; not retained`.
3. Do not identify children, patients, or vulnerable people in the ordinary casefile.
4. Notify counsel promptly and follow counsel's preservation or reporting instructions.
5. If counsel directs preservation, use counsel's approved secure method and access controls; do not improvise a repository.
6. If there is immediate danger, contact emergency services or the appropriate safeguarding authority.

## What the mapper may retain

- Public policies, procedures, aggregate statistics, audits, licensing, accreditation, public notices, and official responses.
- Lawfully obtained records belonging to the authorized person, only when necessary and stored in an approved restricted system.
- A minimal redacted event reference showing that a sensitive issue was routed to counsel, without the underlying content.

## Technical enforcement

- The public collector is for explicitly selected public URLs only; the researcher must exclude sensitive material before collection. A future classifier may warn on likely sensitive content, but no classifier can replace counsel or guarantee legality.
- Restricted references are separated from the public graph and excluded from ordinary exports and search.
- Sensitive content is never sent to analytics, third-party APIs, language models, browser telemetry, or public reporting tools by default.
- Access is least-privilege, logged, time-limited, encrypted, and subject to a retention/deletion decision.
- Any uncertain item is treated as restricted until counsel or an authorized custodian determines otherwise.

## Investigation principle

The objective is lawful accountability and protection, not possession of every possible piece of information. The strongest casefile is the one that preserves relevant proof without creating a second privacy or evidence-handling problem.
