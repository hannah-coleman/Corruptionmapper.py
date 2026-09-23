# Signal Ledger casefile design

## Core idea: Logos

**Logos** is the casefile's reasoning ledger: the explicit chain from observation to source, rule, inference, counterevidence, uncertainty, and next lawful action. A graph edge is never allowed to stand alone. It must resolve to a Logos entry.

```text
Observation -> Source -> Event -> Rule or mechanism -> Inference -> Counterevidence -> Confidence -> Next test
```

The system should preserve the original observation and never silently rewrite it into a conclusion.

## Four evidence lanes

Every item, claim, and relationship belongs to exactly one current lane:

1. **Established:** directly supported by a reliable source, with scope and limitations recorded.
2. **Plausible hypothesis:** a coherent explanation that fits known facts but needs testing.
3. **Emerging circumstance:** an incomplete pattern worth monitoring because it may become relevant; it is not a claim.
4. **Rejected or superseded:** tested, contradicted, withdrawn, or replaced. Preserve the reason and the evidence rather than deleting it.

A lane change requires a dated review note, the reviewer, and the supporting or contrary sources.

## Evidence object

Each observation should contain:

- stable ID and exact transcription
- source, issuing body or account, URL, capture time, and file hash where possible
- event date, location, actors, and record type
- provenance quality and access limitations
- applicable statute, regulation, policy, order, procedure, or scientific standard
- claim scope: what it supports and what it does not support
- linked entities and relationships, each marked direct, inferred, or unresolved
- lane, confidence, corroboration count, and known conflicts
- privacy, privilege, safety, and publication-risk tags
- next test or lawful records request

## Discrepancy model

A discrepancy is a comparison result, not a verdict. Store:

- the two or more exact source passages
- the compared field or proposition
- date and version of each source
- whether the difference is substantive, clerical, temporal, definitional, or unresolved
- possible innocent explanations
- governing rule or expected process
- requested follow-up and response status

Exculpatory findings are not a separate afterthought. They are first-class casefile data: if a discrepancy, omission, version conflict, or procedural defect supports innocence, it must be preserved, labeled, and reviewed with the same rigor as a harmful pattern. The app should never convert a missing record or contradiction into an accusation; it should record what the record does and does not establish.

## Scientific lenses

Physics, biology, pathology, and other technical disciplines may be useful as **review lenses** only when the evidence actually raises a relevant question. The app should ask:

- What observable measurement or record exists?
- What mechanism is being proposed?
- What baseline or control would test it?
- What alternative explanations fit the same observation?
- What expertise, chain of custody, and validated method are required?
- What would falsify the hypothesis?

The app must not diagnose a person, infer medical or forensic causation from symptoms or timing, perform amateur pathology, or convert a scientific-sounding association into proof. Technical conclusions require qualified experts and documented methods.

Example lanes:

- **Physics:** timing, location, signal or energy measurements, equipment logs, environmental conditions.
- **Biology:** specimens, exposure records, chain of custody, validated laboratory results, consent and privacy.
- **Pathology:** official reports, clinical records obtained lawfully, qualified interpretation, differential explanations.

## Micro-to-macro levels

- **Micro:** one statement, timestamp, document version, transaction, call, image, video frame, or policy clause.
- **Meso:** one incident, contract, person, entity, agency, procedure, or response sequence.
- **Macro:** recurring patterns across time, institutions, vendors, jurisdictions, or oversight channels.

A macro pattern may prioritize review, but it cannot elevate a person or organization into an accusation without item-level support.

## Quality gates

Before a claim can be used in a report:

- source and capture metadata are complete
- the exact supporting passage is preserved
- the claim is narrower than or equal to what the source establishes
- a second independent source is sought for material claims
- contradictory and exculpatory evidence is logged
- rule, standard, or comparison baseline is identified
- personal-data and legal-risk review is complete
- counsel or a qualified subject-matter expert reviews specialized conclusions

## Attribution discipline

Ideas and quotations must be verified independently. The popular “energy, frequency, and vibration” quotation attributed to Nikola Tesla is commonly circulated without a reliable primary source. Store it as **unverified attribution**, not as a Tesla quotation or scientific premise.
