import sqlite3

import pytest

from app.storage.db import connect
from app.storage.migrations import MIGRATIONS, SchemaTooNew, current_version, migrate


def open_db(tmp_path):
    path = tmp_path / "app.db"
    return path, connect(path)


def test_fresh_database_gets_latest_schema(tmp_path):
    path, conn = open_db(tmp_path)
    migrate(conn, path)
    assert current_version(conn) == MIGRATIONS[-1][0]
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"settings", "campaigns", "recipients", "attachment_rules"} <= tables


def test_migrate_twice_is_harmless_and_makes_no_backup(tmp_path):
    path, conn = open_db(tmp_path)
    migrate(conn, path)
    migrate(conn, path)
    assert list(tmp_path.glob("*.bak")) == []


def test_upgrade_backs_up_then_applies_and_keeps_data(tmp_path):
    path, conn = open_db(tmp_path)
    v1 = [MIGRATIONS[0]]
    migrate(conn, path, v1)
    conn.execute(
        "INSERT INTO campaigns(name, created_at, updated_at) VALUES ('c','t','t')"
    )

    migrate(conn, path, v1 + [(2, "ALTER TABLE campaigns ADD COLUMN note TEXT;")])

    assert current_version(conn) == 2
    assert conn.execute("SELECT name FROM campaigns").fetchone()[0] == "c"
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1
    old = sqlite3.connect(str(backups[0]))
    assert old.execute("PRAGMA user_version").fetchone()[0] == 1
    old.close()


def test_failed_migration_rolls_back(tmp_path):
    path, conn = open_db(tmp_path)
    v1 = [MIGRATIONS[0]]
    migrate(conn, path, v1)
    broken = v1 + [(2, "ALTER TABLE campaigns ADD COLUMN note TEXT; THIS IS NOT SQL;")]
    with pytest.raises(sqlite3.Error):
        migrate(conn, path, broken)
    assert current_version(conn) == 1
    columns = [r[1] for r in conn.execute("PRAGMA table_info(campaigns)")]
    assert "note" not in columns


def test_database_from_a_newer_app_is_refused(tmp_path):
    path, conn = open_db(tmp_path)
    conn.execute("PRAGMA user_version = 99")
    with pytest.raises(SchemaTooNew):
        migrate(conn, path)
