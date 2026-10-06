from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_V1 = """
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE campaigns (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    subject    TEXT NOT NULL DEFAULT '',
    body_html  TEXT NOT NULL DEFAULT '',
    variables  TEXT NOT NULL DEFAULT '[]',
    state      TEXT NOT NULL DEFAULT 'draft'
               CHECK (state IN ('draft','previewed','running','paused','finished')),
    locked     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE recipients (
    id            INTEGER PRIMARY KEY,
    campaign_id   INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    email         TEXT NOT NULL COLLATE NOCASE,
    values_json   TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','sending','sent','failed','interrupted')),
    error_code    TEXT,
    error_message TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    sent_at       TEXT,
    position      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (campaign_id, email)
);
CREATE INDEX idx_recipients_campaign_status ON recipients(campaign_id, status);

CREATE TABLE attachment_rules (
    id                INTEGER PRIMARY KEY,
    campaign_id       INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    path              TEXT,
    folder            TEXT,
    filename_template TEXT,
    position          INTEGER NOT NULL DEFAULT 0,
    CHECK (
        (path IS NOT NULL AND folder IS NULL AND filename_template IS NULL) OR
        (path IS NULL AND folder IS NOT NULL AND filename_template IS NOT NULL)
    )
);
"""

# (version, sql). Append only; never edit a released migration.
MIGRATIONS: list[tuple[int, str]] = [
    (1, _V1),
    (2, "ALTER TABLE campaigns ADD COLUMN halt_reason TEXT;"),
]


class SchemaTooNew(RuntimeError):
    """The database was created by a newer version of the app."""


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _backup(conn: sqlite3.Connection, db_path: Path, from_version: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.stem}.v{from_version}-{stamp}.bak")
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


def migrate(
    conn: sqlite3.Connection,
    db_path: str | Path | None = None,
    migrations: list[tuple[int, str]] = MIGRATIONS,
) -> None:
    versions = [v for v, _ in migrations]
    if versions != list(range(1, len(versions) + 1)):
        raise ValueError("Migrations must be numbered 1..N without gaps")

    current = current_version(conn)
    latest = versions[-1]
    if current > latest:
        raise SchemaTooNew(
            f"Database is version {current} but this app only knows up to {latest}. "
            "Update the app instead of downgrading."
        )

    pending = [(v, sql) for v, sql in migrations if v > current]
    if not pending:
        return
    if current > 0 and db_path is not None:
        _backup(conn, Path(db_path), current)

    for version, sql in pending:
        script = f"BEGIN;\n{sql}\nPRAGMA user_version = {int(version)};\nCOMMIT;"
        try:
            conn.executescript(script)
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
