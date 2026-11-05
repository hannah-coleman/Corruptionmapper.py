# Corruption mapper implementation plan

## Mission

Build a lawful, evidence-first accountability and intervention-support system that maps corruption, misconduct, and organized abuse patterns without becoming a punishment engine, public shaming platform, or surveillance tool.

## Scope boundaries

The system must:

- preserve provenance and chain-of-custody for every fact
- distinguish public, restricted, and counsel-protected materials
- keep vulnerable persons and minors out of ordinary graph views
- prioritize exculpatory and contradictory evidence
- require human review before escalation
- route findings to lawful oversight or intervention pathways
- support least-intrusive intervention planning

The system must not:

- auto-label people guilty
- infer guilt from weak patterns alone
- expose sensitive identifying details in ordinary exports
- ingest leaked or improperly obtained material
- operate as a public blacklist or punishment engine
- publish shaming reports without review

## Core pillars

### 1. Evidence integrity

- Source metadata: source URL, capture time, source type, access basis, collection limitations
- Hash and raw preservation for collected files
- Observation records with timestamps, source references, and notes
- Evidence ladder: fact, corroborated fact, inference, allegation, contradiction, unresolved lead
- Counterevidence and exculpatory evidence tracked as first-class data

### 2. Governance and review

- Role-based access: owner, researcher, reviewer, counsel, oversight, export-only
- Human review workflow with reviewer identity, date, rationale, and final disposition
- Disposition statuses: supported, contradicted, insufficient evidence, duplicate, out of scope, counsel-review, pending, unresolved
- Appeal and escalation register
- Every material flag must include the rule or process being evaluated and the next lawful action

### 3. Privacy and safety

- Separate public graph and restricted evidence vault
- Protected-subject exclusion rules for minors, victims, witnesses, and vulnerable persons
- Redaction by default for public or shared exports
- Access logging for every restricted record and export
- Quarantine workflow for suspicious or leaked material

### 4. Graph and analytics

- Entities: persons, businesses, agencies, properties, funds, groups, records, jurisdictions
- Events: meetings, contracts, payments, approvals, transfers, incidents, filings, statements
- Relationships labeled direct, inferred, or unresolved
- Timeline and chronology view tied directly to source records
- Network clustering for suspicious patterns, not guilt declarations

### 5. Intervention planning

- Risk classification: privacy risk, retaliation risk, public safety risk, institutional risk
- Intervention options: supervision, monitoring, work requirement, restorative order, treatment, protective relocation, legal referral
- Least-intrusive intervention rule: choose the minimum action that meaningfully reduces risk
- Rehabilitation and reintegration scoring for permissible, humane planning paths

## Milestone plan

### Phase 1: evidence and casefile foundation

Deliverables:

- persistent local database for entities, events, observations, sources, and relationships
- schema versioning and immutable source logs
- normalized import pipeline for JSON and manifest records
- evidence ladder and contradiction fields
- casefile export format for internal review

Acceptance criteria:

- every observation can be traced back to a source
- every claim can be marked as fact, inference, or unresolved
- every contradiction is retained, not hidden

### Phase 2: review and governance layer

Deliverables:

- reviewer workflow and disposition records
- material-risk queue and review prioritization
- export controls for working, counsel, and oversight packets
- audit trail for edits, redactions, and escalations

Acceptance criteria:

- no flag closes without a human disposition
- each export clearly states its purpose and audience
- every restricted record is access-controlled and logged

### Phase 3: public/private separation and safety controls

Deliverables:

- public evidence graph
- restricted evidence vault
- protected-subject exclusion rules
- redaction workflows and policy enforcement
- quarantine handling for likely protected material

Acceptance criteria:

- protected subjects are not visible in ordinary graph views
- risky material is never imported silently
- public exports cannot contain restricted identifiers

### Phase 4: legal relevance and oversight reporting

Deliverables:

- rule and policy linkage for each material issue
- oversight packet builder with chronology, limitations, and source index
- request and response tracker for records requests and formal review
- counsel-ready package generation

Acceptance criteria:

- each material finding maps to a relevant law, process, policy, or standard
- each report distinguishes proof, inference, and unresolved items
- each packet is scoped to its intended audience

### Phase 5: intervention and rehabilitation planning

Deliverables:

- intervention matrix with least-intrusive options
- rehabilitation eligibility logic for structured, humane pathways
- monitored reentry and compliance review model
- integration with oversight and case closure states

Acceptance criteria:

- intervention plans are tied to risk reduction and legal process
- punitive actions are not generated by the app itself
- humane transition pathways are explicitly modeled

## Concrete backlog

### Must-have now

- evidence provenance model
- contradiction and counterevidence registers
- human review status and disposition log
- public/restricted segregation
- protected-subject redaction rules
- evidence ladder and confidence tracking
- export class definitions

### High-value next

- legal relevance engine
- case chronology builder
- review queue and materiality scoring
- counsel packet generator
- oversight packet generator
- intervention planner

### Optional later

- mobile case review companion
- secure field note capture
- dashboards for investigators and oversight bodies
- export to legal or public-interest reporting formats

## Readiness definition

The project is ready for serious government-facing or oversight review only when it can demonstrate:

- every fact has provenance and auditability
- every relationship is explainable and reviewable
- every contradiction is visible
- every export has a lawful purpose and scope
- every vulnerable subject is protected
- every material finding has a human reviewer and disposition
- every intervention is least-intrusive and reviewable

## Recommended next action

Implement Phase 1 and Phase 2 first. They constitute the minimum credible baseline for a government-grade corruption mapper: evidence integrity, reviewability, and privacy-safe governance.
