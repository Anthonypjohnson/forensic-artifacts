CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','utc')),
    last_login      TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    location     TEXT NOT NULL,
    tools        TEXT NOT NULL,
    instructions TEXT NOT NULL,
    significance TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now','utc')),
    created_by   TEXT NOT NULL,
    updated_by   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS artifact_tags (
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    PRIMARY KEY (artifact_id, tag_id)
);

CREATE TABLE IF NOT EXISTS edit_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id    INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    editor_name    TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    changed_at     TEXT NOT NULL DEFAULT (datetime('now','utc')),
    snapshot_json  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_updated ON artifacts(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_artifact  ON edit_history(artifact_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_tags_art ON artifact_tags(artifact_id);

-- IOC tables
CREATE TABLE IF NOT EXISTS ioc_tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS iocs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name     TEXT NOT NULL DEFAULT '',
    severity      TEXT NOT NULL DEFAULT 'Medium',
    hostname      TEXT NOT NULL DEFAULT '',
    ip_address    TEXT NOT NULL DEFAULT '',
    domain        TEXT NOT NULL DEFAULT '',
    url           TEXT NOT NULL DEFAULT '',
    hash_value    TEXT NOT NULL DEFAULT '',
    hash_type     TEXT NOT NULL DEFAULT '',
    filename      TEXT NOT NULL DEFAULT '',
    file_path     TEXT NOT NULL DEFAULT '',
    registry_key  TEXT NOT NULL DEFAULT '',
    command_line  TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    user_account  TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','utc')),
    created_by    TEXT NOT NULL,
    updated_by    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ioc_tag_assignments (
    ioc_id INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES ioc_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (ioc_id, tag_id)
);

CREATE TABLE IF NOT EXISTS ioc_edit_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ioc_id         INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    edited_at      TEXT NOT NULL DEFAULT (datetime('now','utc')),
    editor_name    TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    ioc_snapshot   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_iocs_updated_at    ON iocs(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ioc_history_ioc_id ON ioc_edit_history(ioc_id);
