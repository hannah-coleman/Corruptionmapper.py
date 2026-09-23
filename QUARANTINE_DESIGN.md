# Suspected-sensitive-material quarantine

## Default behavior

When a source appears to contain leaked, hacked, stolen, improperly disclosed, child-welfare, medical, disability, school, or other protected material, Signal Ledger must stop processing it. It must not download, OCR, index, summarize, transmit, or place the content in the ordinary casefile.

Detection is only a warning, not a legal determination. A human with appropriate authority and counsel decides the next step.

## Minimal incident record

The default system may retain only:

- quarantine incident ID
- detection time in UTC
- referring source category and URL or location, only as needed for counsel to identify it
- neutral detection reason, without copying sensitive content
- whether content was not accessed, partially accessed, or already received by the user
- recommended desk: counsel, privacy officer, records custodian, or safety support
- routing status, reviewer, and disposition

Do not store names of children or patients, medical details, images, video frames, document text, credentials, or identifying details in the incident record.

## Counsel-controlled preservation

If counsel directs preservation, use a separate approved system with:

- encryption before storage
- a key held by counsel or an independent authorized custodian, not the ordinary researcher account
- strict role-based access and immutable access logs
- no indexing, search, analytics, third-party API, model, browser telemetry, or public export
- documented legal basis, chain of custody, retention period, and destruction/return instruction
- a redacted reference in Signal Ledger rather than the original content

A local app cannot honestly promise that its owner can never access a file if that owner controls the operating system, backups, or encryption keys. That separation requires independent key custody or an external counsel-managed repository.

## Routing outcomes

- `not-accessed`: record minimal metadata and notify counsel.
- `received-in-error`: do not forward or copy; preserve only the minimum routing information counsel requests.
- `counsel-preservation-directed`: transfer only through counsel's approved secure process.
- `confirmed-public-and-lawful`: counsel or the authorized custodian documents the basis before any ordinary import.
- `false-positive`: record why the warning was cleared without retaining unnecessary sensitive content.

## Why this matters

The goal is to protect children, patients, witnesses, and the integrity of the case. Possessing or redistributing leaked information can create a new legal and ethical problem, even when the original purpose is accountability.
