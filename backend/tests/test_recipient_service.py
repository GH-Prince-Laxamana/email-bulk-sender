from __future__ import annotations

import pytest

from app.services.recipients import RecipientError, RecipientService
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


def test_import_csv_creates_recipients_and_variables(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    result = service.import_csv(
        campaign_id,
        "email,Name,Company\n"
        "alice@example.com,Alice,Acme\n"
        "bob@example.com,Bob,Globex\n",
    )

    assert result == {
        "inserted": 2,
        "ignored_duplicates": 0,
        "total_rows": 2,
    }

    recipients = service.list(campaign_id)

    assert [(r["email"], r["values"], r["status"]) for r in recipients] == [
        ("alice@example.com", {"Name": "Alice", "Company": "Acme"}, "pending"),
        ("bob@example.com", {"Name": "Bob", "Company": "Globex"}, "pending"),
    ]


def test_import_csv_supports_tab_separated_paste(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    result = service.import_csv(
        campaign_id,
        "email\tName\tCompany\n" "alice@example.com\tAlice\tAcme\n",
    )

    assert result["inserted"] == 1

    recipient = service.list(campaign_id)[0]

    assert recipient["email"] == "alice@example.com"
    assert recipient["values"] == {
        "Name": "Alice",
        "Company": "Acme",
    }


def test_import_collapses_duplicate_emails_case_insensitively(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    result = service.import_csv(
        campaign_id,
        "email,Name\n"
        "Alice@example.com,Alice\n"
        "alice@EXAMPLE.com,Other\n"
        "Bob@example.com,Bob\n",
    )

    assert result == {
        "inserted": 2,
        "ignored_duplicates": 0,
        "total_rows": 2,
    }

    recipients = service.list(campaign_id)

    assert [(r["email"], r["values"]) for r in recipients] == [
        ("Alice@example.com", {"Name": "Alice"}),
        ("Bob@example.com", {"Name": "Bob"}),
    ]


def test_existing_database_duplicates_are_ignored(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email,Name\n" "alice@example.com,Alice\n",
    )

    result = service.import_csv(
        campaign_id,
        "email,Name\n" "ALICE@EXAMPLE.COM,Changed\n" "bob@example.com,Bob\n",
    )

    assert result == {
        "inserted": 1,
        "ignored_duplicates": 1,
        "total_rows": 2,
    }

    recipients = service.list(campaign_id)

    assert [(r["email"], r["values"]) for r in recipients] == [
        ("alice@example.com", {"Name": "Alice"}),
        ("bob@example.com", {"Name": "Bob"}),
    ]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty_import"),
        ("Name,Company\nAlice,Acme\n", "missing_email_column"),
        ("email,email\nalice@example.com,other\n", "duplicate_email_column"),
        ("email,,Company\nalice@example.com,Alice,Acme\n", "invalid_header"),
        ("email,Name,Name\nalice@example.com,Alice,A\n", "duplicate_column"),
        ("email,Name\nalice@example.com\n", "invalid_row"),
    ],
)
def test_invalid_import_is_rejected(db, text, code):
    conn, campaign_id = db
    service = RecipientService(conn)

    with pytest.raises(RecipientError) as exc_info:
        service.import_csv(campaign_id, text)

    assert exc_info.value.code == code


def test_blank_email_is_rejected(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    with pytest.raises(RecipientError) as exc_info:
        service.import_csv(
            campaign_id,
            "email,Name\n" ",Alice\n",
        )

    assert exc_info.value.code == "missing_email"


def test_recipient_import_resets_preview_to_draft(db):
    conn, campaign_id = db

    conn.execute(
        "UPDATE campaigns SET state = 'previewed' WHERE id = ?",
        (campaign_id,),
    )

    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email,Name\n" "alice@example.com,Alice\n",
    )

    campaign = repo.get_campaign(conn, campaign_id)

    assert campaign is not None
    assert campaign.state == "draft"


def test_locked_campaign_cannot_import_recipients(db):
    conn, campaign_id = db

    conn.execute(
        "UPDATE campaigns SET locked = 1 WHERE id = ?",
        (campaign_id,),
    )

    service = RecipientService(conn)

    with pytest.raises(RecipientError) as exc_info:
        service.import_csv(
            campaign_id,
            "email\nalice@example.com\n",
        )

    assert exc_info.value.code == "campaign_locked"


def test_running_campaign_cannot_import_recipients(db):
    conn, campaign_id = db

    conn.execute(
        "UPDATE campaigns SET state = 'running' WHERE id = ?",
        (campaign_id,),
    )

    service = RecipientService(conn)

    with pytest.raises(RecipientError) as exc_info:
        service.import_csv(
            campaign_id,
            "email\nalice@example.com\n",
        )

    assert exc_info.value.code == "campaign_running"


def test_retry_failed_recipients(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email\nalice@example.com\nbob@example.com\n",
    )

    recipients = repo.list_recipients(conn, campaign_id)

    repo.mark_failed(
        conn,
        recipients[0].id,
        "recipient_rejected",
        "No such user",
    )

    changed = service.retry_failed(campaign_id)

    assert changed == 1
    assert (
        repo.get_recipient(
            conn,
            recipients[0].id,
        ).status
        == "pending"
    )


def test_resolve_interrupted_as_retry(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email\nalice@example.com\n",
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]

    repo.mark_interrupted(
        conn,
        recipient.id,
        "app_stopped",
        "The app stopped.",
    )

    service.resolve_interrupted(
        recipient.id,
        retry=True,
    )

    resolved = repo.get_recipient(
        conn,
        recipient.id,
    )

    assert resolved is not None
    assert resolved.status == "pending"


def test_resolve_interrupted_as_sent(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email\nalice@example.com\n",
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]

    repo.mark_interrupted(
        conn,
        recipient.id,
        "app_stopped",
        "The app stopped.",
    )

    service.resolve_interrupted(
        recipient.id,
        retry=False,
    )

    resolved = repo.get_recipient(
        conn,
        recipient.id,
    )

    assert resolved is not None
    assert resolved.status == "sent"
    assert resolved.sent_at is not None


def test_resolve_non_interrupted_recipient_is_rejected(db):
    conn, campaign_id = db
    service = RecipientService(conn)

    service.import_csv(
        campaign_id,
        "email\nalice@example.com\n",
    )

    recipient = repo.list_recipients(conn, campaign_id)[0]

    with pytest.raises(RecipientError) as exc_info:
        service.resolve_interrupted(
            recipient.id,
            retry=True,
        )

    assert exc_info.value.code == "recipient_not_interrupted"
