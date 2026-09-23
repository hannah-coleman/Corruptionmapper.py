# Public-record collector

Use this only for explicitly selected, publicly accessible URLs relevant to a defined audit question.

## Run

1. Copy `targets.example.txt` to `targets.txt`.
2. Add one official public URL per line.
3. Review the list with counsel before collection.
4. Run:

```bash
python3 collector.py targets.txt --output evidence/raw
```

The collector checks `robots.txt`, uses a descriptive user agent, waits between requests, limits response size, and does not follow links or authenticate. It stores raw responses under `evidence/raw` and appends provenance records to `evidence/manifest.jsonl`.

Do not place leaked, hacked, stolen, or improperly disclosed child, medical, disability, school, or other protected material in the target list. Do not use this collector for those materials. See `SENSITIVE_DATA_POLICY.md`.

## Bounded site discovery

When counsel and the source owner/terms permit following public links within an official site, use explicit seed URLs:

```bash
python3 discover_public.py https://approved.example.gov/public-records --max-pages 50 --max-depth 2
```

This stays on the approved seed hosts, honors `robots.txt`, rate-limits requests, caps response size, and records denials. It does not follow links to other hosts or bypass access controls.

## Compile collected material for search

```bash
python3 index_evidence.py evidence/manifest.jsonl evidence/discovery-manifest.jsonl
```

The local full-text index preserves the source URL, capture timestamp, raw-file path, and hash. Indexing does not verify a claim; review the original source and add the observation to the casefile before treating it as evidence.

## Promote discovery snapshots

To place collected pages into the casefile as source records without creating claims:

```bash
python3 import_discovery.py evidence/discovery-manifest.jsonl
```

This is intentionally source-only. A human must review the original snapshot and create any observation, entity, relationship, or discrepancy explicitly.

## What to record in the case file

For each collected item, add the issuing agency or account, record title, original URL, publication date, capture time in UTC, page/paragraph or video timestamp, exact relevant text, what it proves, linked nodes, confidence, and contradictions. A downloaded item is not automatically verified; review its origin and content first.

## Suggested first target list

Keep the first pass narrow: one contract or incident, its official agency page, meeting materials, payment records, related business filings, and any public statement responding to it. Expand only when a source creates a specific, documented next question.

## Analyze discrepancies

After reviewing and normalizing collected material into the JSON shape shown in `records.example.json`, run:

```bash
python3 audit_engine.py records.json --output evidence/flags.json
```

The engine works from **micro to macro**:

- **Micro:** missing provenance, contradictory field values, dates, and source duplication.
- **Meso:** records grouped around a person, entity, contract, agency, or event.
- **Macro:** the resulting flags and relationships can be reviewed in the graph for recurring procedural patterns.

Flags are prompts for human review, not findings of corruption. Before elevating a pattern, verify the source, compare the governing procedure, seek a second independent source, and record an innocent explanation if one exists.
