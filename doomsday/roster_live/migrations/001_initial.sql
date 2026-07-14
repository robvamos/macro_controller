CREATE TABLE IF NOT EXISTS LiveRosterSchema (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS RosterCaptureSessions (
    session_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    runtime_id TEXT NOT NULL,
    capture_method TEXT NOT NULL,
    game_version TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS RosterCaptureArtifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES RosterCaptureSessions(session_id),
    stage TEXT NOT NULL,
    hero_id TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(session_id, sha256)
);

CREATE TABLE IF NOT EXISTS RosterObservationCandidates (
    candidate_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES RosterCaptureSessions(session_id),
    artifact_id TEXT NOT NULL REFERENCES RosterCaptureArtifacts(artifact_id),
    hero_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    proposed_json TEXT NOT NULL,
    normalized_hash TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    observed_at TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    stage TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    locale TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_roster_candidates_session_field
    ON RosterObservationCandidates(session_id, hero_id, field_name, confidence DESC);

CREATE TABLE IF NOT EXISTS RosterChangeSets (
    change_set_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES RosterCaptureSessions(session_id),
    base_revision INTEGER NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    committed_revision INTEGER,
    failure_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS RosterChangeItems (
    item_id TEXT PRIMARY KEY,
    change_set_id TEXT NOT NULL REFERENCES RosterChangeSets(change_set_id),
    candidate_id TEXT NOT NULL REFERENCES RosterObservationCandidates(candidate_id),
    hero_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    current_json TEXT,
    proposed_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_ref TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    conflict INTEGER NOT NULL,
    alternatives_json TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'unresolved',
    override_json TEXT,
    decision_reason TEXT NOT NULL DEFAULT '',
    UNIQUE(change_set_id, hero_id, field_name)
);

CREATE TABLE IF NOT EXISTS RosterRevisions (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_revision INTEGER NOT NULL,
    change_set_id TEXT NOT NULL UNIQUE REFERENCES RosterChangeSets(change_set_id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS RosterHeroes (
    hero_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS RosterHeroFacts (
    hero_id TEXT NOT NULL REFERENCES RosterHeroes(hero_id),
    field_name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    revision_id INTEGER NOT NULL REFERENCES RosterRevisions(revision_id),
    candidate_id TEXT NOT NULL REFERENCES RosterObservationCandidates(candidate_id),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(hero_id, field_name)
);

CREATE TABLE IF NOT EXISTS RosterFactHistory (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id INTEGER NOT NULL REFERENCES RosterRevisions(revision_id),
    hero_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_json TEXT,
    new_json TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS RosterCommitAudit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_set_id TEXT NOT NULL,
    revision_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS RosterEvidenceOutbox (
    outbox_id TEXT PRIMARY KEY,
    revision_id INTEGER NOT NULL REFERENCES RosterRevisions(revision_id),
    candidate_id TEXT NOT NULL REFERENCES RosterObservationCandidates(candidate_id),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    published_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_roster_outbox_status
    ON RosterEvidenceOutbox(status, created_at);
