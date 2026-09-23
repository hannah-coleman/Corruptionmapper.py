# CourtConnect and court-record workflow

CourtConnect should be a source adapter for **lawfully accessible Arkansas court information**, subject to the service's current terms, access controls, rate limits, and any court restrictions. Availability in a public search interface does not mean every document may be copied, republished, or used without review.

## What to capture

- Court, county, division, case number, case type, filing date, and current status.
- Parties and attorney roles exactly as shown, with identity-disambiguation notes.
- Docket events, orders, judgments, hearing dates, filings, and publicly downloadable exhibits where access is permitted.
- Original case or document URL, access date/time in UTC, document title, page count, and SHA-256 hash of a downloaded file where lawful.
- The exact proposition supported by the item, limitations, redactions, sealed or restricted indicators, and related cases.

## What not to do

- Do not bypass CAPTCHA, authentication, paywalls, rate limits, robots restrictions, sealed-record controls, or technical barriers.
- Do not create accounts under false identities or use another person's credentials.
- Do not bulk-download unrelated cases or collect sensitive information beyond the defined audit question.
- Do not treat an allegation in a pleading, a docket entry, a dismissal, or an arrest record as proof of misconduct.
- Do not publish protected identifiers, addresses, medical information, information about minors, or sealed material.

## Verification rules

- A docket entry establishes that an event was recorded, not that every statement in a filing is true.
- Read the order, judgment, disposition, and appeal status before summarizing a case outcome.
- Track amendments, superseding filings, corrections, and later orders.
- Separate party allegations, attorney argument, judicial findings, admitted facts, and disputed facts.
- Corroborate material claims with the court's order or another independent primary source.

## When a request is needed

For Arkansas state or local records, use the applicable Arkansas public-records process or the court clerk's established request procedure, verified with counsel. Federal FOIA applies to federal agencies, not Arkansas courts, the City of Paragould, or Greene County. Subpoenas, discovery, preservation letters, confidential filings, sealed records, and requests involving protected information belong with counsel.

## Casefile fields

Use source type `court-record`, status values such as `docket-confirmed`, `filing-allegation`, `judicial-finding`, `dismissed`, `pending`, or `needs-review`, and always preserve the proceeding's procedural posture. A case connection is not evidence of guilt.
