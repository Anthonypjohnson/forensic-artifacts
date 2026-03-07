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
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    category         TEXT NOT NULL DEFAULT '',
    severity         TEXT NOT NULL DEFAULT 'Medium',
    hostname         TEXT NOT NULL DEFAULT '',
    ip_address       TEXT NOT NULL DEFAULT '',
    domain           TEXT NOT NULL DEFAULT '',
    url              TEXT NOT NULL DEFAULT '',
    hash_value       TEXT NOT NULL DEFAULT '',
    hash_type        TEXT NOT NULL DEFAULT '',
    filename         TEXT NOT NULL DEFAULT '',
    file_path        TEXT NOT NULL DEFAULT '',
    registry_key     TEXT NOT NULL DEFAULT '',
    command_line     TEXT NOT NULL DEFAULT '',
    email            TEXT NOT NULL DEFAULT '',
    user_account     TEXT NOT NULL DEFAULT '',
    notes            TEXT NOT NULL DEFAULT '',
    user_agent       TEXT NOT NULL DEFAULT '',
    mitre_category   TEXT NOT NULL DEFAULT '',
    detection_rule   TEXT NOT NULL DEFAULT '',
    network_port     TEXT NOT NULL DEFAULT '',
    network_protocol TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','utc')),
    created_by       TEXT NOT NULL,
    updated_by       TEXT NOT NULL
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

-- Events tables
CREATE TABLE IF NOT EXISTS events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ioc_id            INTEGER REFERENCES iocs(id) ON DELETE SET NULL,
    show_on_timeline  INTEGER NOT NULL DEFAULT 1,
    event_category    TEXT,
    system            TEXT,
    account           TEXT,
    event_datetime    TEXT,
    high_level_source TEXT,
    detailed_source   TEXT,
    notes             TEXT,
    screenshot_path   TEXT,
    task_id           TEXT,
    linked_task_id    INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by        TEXT NOT NULL DEFAULT '',
    updated_by        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS event_tag_assignments (
    event_id  INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    tag_id    INTEGER NOT NULL REFERENCES ioc_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, tag_id)
);

CREATE TABLE IF NOT EXISTS event_edit_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    editor_name    TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    edited_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    snapshot_json  TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_datetime        ON events(event_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_events_ioc_id          ON events(ioc_id);
CREATE INDEX IF NOT EXISTS idx_events_linked_task_id  ON events(linked_task_id);
CREATE INDEX IF NOT EXISTS idx_event_history_event_id ON event_edit_history(event_id);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Open',
    priority    TEXT NOT NULL DEFAULT 'Medium',
    assignee    TEXT,
    description TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    created_by  TEXT NOT NULL DEFAULT '',
    updated_by  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- Global application settings (key/value)
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
