from __future__ import annotations

import pytest

from app.storage import repo
from app.storage.db import connect
from app.storage.migrations import migrate


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = connect(path)
    migrate(conn, path)

    campaign_id = repo.create_campaign(
        conn,
        name="Recipients",
    )

    yield conn, campaign_id
    conn.close()


def test_insert_and_list_recipients(db):
    conn, campaign_id = db

    inserted = repo.insert_recipients(
        conn,
        campaign_id,
        [
            ("a@example.com", {"Name": "Alice"}),
            ("b@example.com", {"Name": "Bob"}),
        ],
    )

    assert inserted == 2

    recipients = repo.list_recipients(conn, campaign_id)

    assert [(r.email, r.values, r.status, r.position) for r in recipients] == [
        ("a@example.com", {"Name": "Alice"}, "pending", 0),
        ("b@example.com", {"Name": "Bob"}, "pending", 1),
    ]


def test_duplicate_email_is_ignored_case_insensitively(db):
    conn, campaign_id = db

    inserted = repo.insert_recipients(
        conn,
        campaign_id,
        [
            ("Alice@example.com", {"Name": "Alice"}),
            ("alice@EXAMPLE.com", {"Name": "Different"}),
        ],
    )

    assert inserted == 1

    recipients = repo.list_recipients(conn, campaign_id)

    assert len(recipients) == 1
    assert recipients[0].email == "Alice@example.com"
    assert recipients[0].values == {"Name": "Alice"}


def test_insert_appends_after_existing_positions(db):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [("a@example.com", {})],
    )

    repo.insert_recipients(
        conn,
        campaign_id,
        [
            ("b@example.com", {}),
            ("c@example.com", {}),
        ],
    )

    recipients = repo.list_recipients(conn, campaign_id)

    assert [(r.email, r.position) for r in recipients] == [
        ("a@example.com", 0),
        ("b@example.com", 1),
        ("c@example.com", 2),
    ]


def test_get_recipient_returns_detail_fields(db):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [("a@example.com", {"Name": "Alice"})],
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]
    row = repo.get_recipient(conn, recipient.id)

    assert row is not None
    assert row.id == recipient.id
    assert row.email == "a@example.com"
    assert row.values == {"Name": "Alice"}
    assert row.status == "pending"
    assert row.error_code is None
    assert row.error_message is None
    assert row.attempts == 0
    assert row.sent_at is None


def test_retry_failed_returns_failed_recipients_to_pending(db):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [
            ("a@example.com", {}),
            ("b@example.com", {}),
        ],
    )

    recipients = repo.list_recipients(conn, campaign_id)

    repo.mark_failed(
        conn,
        recipients[0].id,
        "recipient_rejected",
        "No such user",
    )

    changed = repo.retry_failed(conn, campaign_id)

    assert changed == 1

    rows = repo.list_recipients(conn, campaign_id)

    assert rows[0].status == "pending"
    assert rows[0].error_code is None
    assert rows[0].error_message is None
    assert rows[1].status == "pending"


def test_retry_failed_does_not_change_sent_recipients(db):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [
            ("a@example.com", {}),
            ("b@example.com", {}),
        ],
    )

    recipients = repo.list_recipients(conn, campaign_id)

    repo.mark_sent(conn, recipients[0].id)

    changed = repo.retry_failed(conn, campaign_id)

    assert changed == 0
    assert repo.get_recipient(conn, recipients[0].id).status == "sent"


@pytest.mark.parametrize("retry", [True, False])
def test_resolve_interrupted(db, retry):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [("a@example.com", {})],
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]

    repo.mark_interrupted(
        conn,
        recipient.id,
        "app_stopped",
        "The app stopped.",
    )

    repo.resolve_interrupted(
        conn,
        recipient.id,
        retry=retry,
    )

    resolved = repo.get_recipient(conn, recipient.id)

    assert resolved is not None

    if retry:
        assert resolved.status == "pending"
        assert resolved.sent_at is None
    else:
        assert resolved.status == "sent"
        assert resolved.sent_at is not None

    assert resolved.error_code is None
    assert resolved.error_message is None


def test_resolve_interrupted_does_nothing_for_non_interrupted(db):
    conn, campaign_id = db

    repo.insert_recipients(
        conn,
        campaign_id,
        [("a@example.com", {})],
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]

    repo.resolve_interrupted(
        conn,
        recipient.id,
        retry=True,
    )

    resolved = repo.get_recipient(conn, recipient.id)

    assert resolved is not None
    assert resolved.status == "pending"
