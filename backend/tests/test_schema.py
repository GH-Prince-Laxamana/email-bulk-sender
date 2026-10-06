import sqlite3

import pytest

from app.storage.db import connect, transaction
from app.storage.migrations import migrate


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "t.db"
    connection = connect(path)
    migrate(connection, path)
    yield connection
    connection.close()


def add_campaign(conn):
    cur = conn.execute(
        "INSERT INTO campaigns(name, created_at, updated_at) VALUES ('c','now','now')"
    )
    return cur.lastrowid


def add_recipient(conn, campaign_id, email):
    conn.execute(
        "INSERT INTO recipients(campaign_id, email) VALUES (?, ?)", (campaign_id, email)
    )


def add_rule(conn, campaign_id, path=None, folder=None, template=None):
    conn.execute(
        "INSERT INTO attachment_rules(campaign_id, path, folder, filename_template) "
        "VALUES (?, ?, ?, ?)",
        (campaign_id, path, folder, template),
    )


def test_email_is_unique_per_campaign_ignoring_case(conn):
    cid = add_campaign(conn)
    add_recipient(conn, cid, "Ana@Example.com")
    with pytest.raises(sqlite3.IntegrityError):
        add_recipient(conn, cid, "ana@example.com")


def test_same_email_is_allowed_in_different_campaigns(conn):
    add_recipient(conn, add_campaign(conn), "ana@example.com")
    add_recipient(conn, add_campaign(conn), "ana@example.com")


def test_deleting_a_campaign_removes_its_children(conn):
    cid = add_campaign(conn)
    add_recipient(conn, cid, "ana@example.com")
    add_rule(conn, cid, path="/tmp/flyer.pdf")
    conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
    assert conn.execute("SELECT COUNT(*) FROM recipients").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM attachment_rules").fetchone()[0] == 0


def test_invalid_recipient_status_is_rejected(conn):
    cid = add_campaign(conn)
    add_recipient(conn, cid, "ana@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE recipients SET status = 'bogus'")


def test_attachment_rule_must_be_exactly_one_form(conn):
    cid = add_campaign(conn)
    add_rule(conn, cid, path="/tmp/a.pdf")
    add_rule(conn, cid, folder="/tmp/certs", template="{{Name}}.pdf")
    with pytest.raises(sqlite3.IntegrityError):
        add_rule(conn, cid, path="/tmp/a.pdf", folder="/tmp/certs", template="x.pdf")
    with pytest.raises(sqlite3.IntegrityError):
        add_rule(conn, cid, folder="/tmp/certs")


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError):
        with transaction(conn):
            add_campaign(conn)
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 0
