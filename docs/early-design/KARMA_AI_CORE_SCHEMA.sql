-- Shared fact-first schema for Karma AI core
-- This is intended to support local case investigation, source tracking, FOIA workflows,
-- and modular chapter integrations.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    jurisdiction_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    owner TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    full_name TEXT,
    aliases_json TEXT NOT NULL,
    role TEXT,
    agency TEXT,
    category TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS agencies (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    name TEXT NOT NULL,
    jurisdiction TEXT,
    agency_type TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    label TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS addresses (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    raw_address TEXT,
    city TEXT,
    county TEXT,
    state TEXT,
    zip_code TEXT,
    normalized_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    title TEXT,
    source_type TEXT NOT NULL,
    issuing_body TEXT,
    url TEXT,
    file_path TEXT,
    captured_at TEXT,
    published_at TEXT,
    status TEXT NOT NULL DEFAULT 'collected',
    content_hash TEXT,
    notes TEXT,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    title TEXT NOT NULL,
    record_type TEXT,
    source_id TEXT,
    agency_id TEXT,
    request_id TEXT,
    record_date TEXT,
    notes TEXT,
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(source_id) REFERENCES sources(id),
    FOREIGN KEY(agency_id) REFERENCES agencies(id)
);

CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    agency_id TEXT,
    jurisdiction TEXT,
    custodian TEXT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TEXT,
    deadline TEXT,
    response_at TEXT,
    denial_reason TEXT,
    counsel_review TEXT,
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(agency_id) REFERENCES agencies(id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_status TEXT NOT NULL DEFAULT 'unresolved',
    source_ids_json TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    source_id TEXT,
    record_id TEXT,
    claim_text TEXT NOT NULL,
    claim_type TEXT NOT NULL DEFAULT 'fact',
    confidence TEXT NOT NULL DEFAULT 'unrated',
    review_status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id),
    FOREIGN KEY(source_id) REFERENCES sources(id),
    FOREIGN KEY(record_id) REFERENCES records(id)
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    confidence TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS review_events (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    reviewer TEXT,
    event_type TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS ai_agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapter_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
