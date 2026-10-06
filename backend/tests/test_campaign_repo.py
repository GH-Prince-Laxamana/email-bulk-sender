from __future__ import annotations

import json

import pytest

from app.storage import repo
from app.storage.db import connect
from app.storage.migrations import migrate


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = connect(path)
    migrate(conn, path)
    yield conn
    conn.close()


def test_create_campaign_starts_as_draft(db):
    campaign_id = repo.create_campaign(
        db,
        name="Test Campaign",
        subject="Hello {{Name}}",
        body_html="<p>Hi {{Name}}</p>",
        variables=["Name"],
    )

    campaign = repo.get_campaign(db, campaign_id)

    assert campaign is not None
    assert campaign.name == "Test Campaign"
    assert campaign.subject == "Hello {{Name}}"
    assert campaign.body_html == "<p>Hi {{Name}}</p>"
    assert campaign.state == "draft"
    assert campaign.locked is False
    assert campaign.halt_reason is None


def test_list_campaigns_returns_newest_first(db):
    first = repo.create_campaign(db, name="First")
    second = repo.create_campaign(db, name="Second")

    campaigns = repo.list_campaigns(db)

    assert [c.id for c in campaigns] == [second, first]


def test_update_campaign_content_does_not_change_lock_or_state(db):
    campaign_id = repo.create_campaign(
        db,
        name="Original",
        subject="Old",
        body_html="Old body",
        variables=["Name"],
    )

    db.execute(
        "UPDATE campaigns SET state = 'previewed', locked = 0 WHERE id = ?",
        (campaign_id,),
    )

    repo.update_campaign_content(
        db,
        campaign_id,
        name="Updated",
        subject="New",
        body_html="New body",
        variables=["First Name"],
    )

    campaign = repo.get_campaign(db, campaign_id)

    assert campaign is not None
    assert campaign.name == "Updated"
    assert campaign.subject == "New"
    assert campaign.body_html == "New body"
    assert json.loads(
        db.execute(
            "SELECT variables FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()["variables"]
    ) == ["First Name"]
    assert campaign.state == "previewed"
    assert campaign.locked is False


def test_duplicate_starts_unlocked_and_draft(db):
    source_id = repo.create_campaign(
        db,
        name="Source",
        subject="Subject",
        body_html="<p>Body</p>",
        variables=["Name"],
    )

    new_id = repo.duplicate_campaign(
        db,
        source_id,
        new_name="Copy",
    )

    source = repo.get_campaign(db, source_id)
    copy = repo.get_campaign(db, new_id)

    assert source is not None
    assert copy is not None

    assert copy.id != source.id
    assert copy.name == "Copy"
    assert copy.subject == source.subject
    assert copy.body_html == source.body_html
    assert copy.state == "draft"
    assert copy.locked is False


def test_duplicate_copies_attachment_rules(db, tmp_path):
    source_id = repo.create_campaign(db, name="Source")

    db.execute(
        "INSERT INTO attachment_rules "
        "(campaign_id, path, position) VALUES (?, ?, ?)",
        (source_id, str(tmp_path / "file.pdf"), 0),
    )

    new_id = repo.duplicate_campaign(
        db,
        source_id,
        new_name="Copy",
    )

    row = db.execute(
        "SELECT path, folder, filename_template, position "
        "FROM attachment_rules WHERE campaign_id = ?",
        (new_id,),
    ).fetchone()

    assert tuple(row) == (
        str(tmp_path / "file.pdf"),
        None,
        None,
        0,
    )


def test_duplicate_does_not_carry_recipients_by_default(db):
    source_id = repo.create_campaign(db, name="Source")

    db.execute(
        "INSERT INTO recipients "
        "(campaign_id, email, values_json, status, attempts, position) "
        "VALUES (?, ?, ?, 'sent', 3, 0)",
        (source_id, "person@example.com", '{"Name":"Prince"}'),
    )

    new_id = repo.duplicate_campaign(
        db,
        source_id,
        new_name="Copy",
    )

    count = db.execute(
        "SELECT COUNT(*) FROM recipients WHERE campaign_id = ?",
        (new_id,),
    ).fetchone()[0]

    assert count == 0


def test_duplicate_can_carry_recipients_as_pending(db):
    source_id = repo.create_campaign(db, name="Source")

    db.execute(
        "INSERT INTO recipients "
        "(campaign_id, email, values_json, status, attempts, position) "
        "VALUES (?, ?, ?, 'sent', 4, 2)",
        (source_id, "person@example.com", '{"Name":"Prince"}'),
    )

    new_id = repo.duplicate_campaign(
        db,
        source_id,
        new_name="Copy",
        carry_recipients=True,
    )

    row = db.execute(
        "SELECT email, values_json, status, attempts, position "
        "FROM recipients WHERE campaign_id = ?",
        (new_id,),
    ).fetchone()

    assert tuple(row) == (
        "person@example.com",
        '{"Name":"Prince"}',
        "pending",
        0,
        2,
    )


def test_duplicate_missing_campaign_raises(db):
    with pytest.raises(ValueError, match="Campaign not found"):
        repo.duplicate_campaign(
            db,
            999,
            new_name="Copy",
        )
