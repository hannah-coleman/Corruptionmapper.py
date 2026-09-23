# Karma AI architecture

## Product direction

Karma AI is a fact-first investigative platform built around a shared evidence graph and modular extensions. It is not a single closed app; it is a platform with a common core and interchangeable chapters for specific investigative tasks.

The design goal is simple:
- one truth model
- many tools
- human review is required
- all claims remain traceable to sources
- each chapter can operate alone or in a shared network

## Core principles

1. Fact-first data model
   - Every claim must be linked to a source and a confidence level.
   - No unsupported conclusions are treated as facts.
   - Evidence must preserve provenance, chain of custody, and review status.

2. Shared intelligence graph
   - People, agencies, entities, addresses, funds, records, and incidents share one graph.
   - A single object can appear across many chapters without duplicating the underlying record.

3. Modular chapter system
   - Investigation chapters operate as independent tools with shared infrastructure.
   - Chapters can be enabled or disabled by role or workflow.
   - A chapter may be a local tool, a linked service, or a curated analysis module.

4. Human review as a required gate
   - AI assists but does not replace legal or ethical review.
   - Findings are labeled as sourced fact, inference, or unresolved lead.
   - Sensitive material is segregated by policy and review status.

5. Collaboration without collapse into a black box
   - Different AI agents have different roles.
   - The system is built for collaboration, not hidden automation.
   - Users can inspect, override, and audit any conclusion.

## Core system layers

### 1. Core database layer
The core database holds all shared entities and evidence:
- cases
- persons
- agencies
- entities
- records
- requests
- sources
- relationships
- evidence
- findings
- review history

### 2. Evidence and provenance layer
This layer governs:
- source URLs and files
- capture timestamps
- hashes
- custody records
- permissions and redactions
- what was observed versus what was inferred

### 3. Graph and relationship layer
This layer links data across:
- person-to-person
- person-to-agency
- agency-to-record
- entity-to-address
- entity-to-fund
- record-to-request
- request-to-response

### 4. Workflow and review layer
This layer supports:
- intake
- scope definition
- record requests
- review routing
- legal caution flags
- denial and exemption tracking
- export and archive

### 5. AI collaborator layer
Different specialists can operate as independent agents:
- source verifier
- entity matcher
- anomaly detector
- timeline builder
- legal workflow assistant
- report writer
- fact-check reviewer

### 6. Extension layer
Each chapter is a tool that uses the same core data model but focuses on a task.

## Recommended chapter model

### A. Local records chapter
Purpose: map local government, county, and state public-record sources.
Focus:
- meeting agendas and minutes
- contract files
- budgets
- permits
- audit records
- public notices

### B. FOIA and records-request chapter
Purpose: turn questions into lawful requests and preserve responses.
Focus:
- agency routing
- request drafting
- deadlines
- exemption tracking
- denials and appeals

### C. Cold case chapter
Purpose: maintain historical and unresolved cases with searchable cross-reference intelligence.
Focus:
- case timelines
- witness links
- public records trails
- unresolved inconsistencies

### D. Law enforcement review chapter
Purpose: review public-facing records, personnel-related public disclosures, and audit-relevant patterns.
Focus:
- agency records
- public complaints
- discipline history
- training and policy issues
- public documentation only

### E. Ethics and oversight chapter
Purpose: compile patterns in campaign finance, governance, and regulatory compliance signals.
Focus:
- disclosures
- ethics filings
- audit findings
- procurement irregularities

### F. Anomaly detection chapter
Purpose: identify recurring patterns across documents, sources, and entities.
Focus:
- shared addresses
- repeated vendors
- missing payment trails
- recurring approvals
- timeline inconsistencies

### G. Reporting and evidence export chapter
Purpose: present fact-based summaries and evidence bundles.
Focus:
- review-ready reports
- timelines
- evidence indexes
- case summaries
- redacted or counsel-reviewed export

## Shared infrastructure standards

Every chapter should follow these rules:
- source-backed claims only
- labels for fact/inference/lead
- support for local, public, or restricted records
- explicit jurisdiction scoping
- human review checkpoints
- no unsupported claim promotion

## Core design recommendation

Build the first version as:
- one shared core database
- one local web dashboard
- modular extension folders
- extension registry with enable/disable toggles
- plugin-style APIs for future tools

This keeps the system flexible while preserving the fact-first operating model.

## Long-term aspiration

Karma AI should become a local intelligence framework that supports:
- public-record review
- cold-case analysis
- oversight mapping
- entity and relationship analysis
- lawful data gathering and review
- collaborative human + AI decision support

It should be powerful, but never opaque.
