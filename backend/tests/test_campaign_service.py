from __future__ import annotations

import pytest

from app.services.campaigns import CampaignError, CampaignService
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


def test_create_returns_draft_campaign(db):
    service = CampaignService(db)

    campaign = service.create(
        name="Newsletter",
        subject="Hello {{Name}}",
        body_html="<p>Hi {{Name}}</p>",
        variables=["Name"],
    )

    assert campaign["name"] == "Newsletter"
    assert campaign["subject"] == "Hello {{Name}}"
    assert campaign["body_html"] == "<p>Hi {{Name}}</p>"
    assert campaign["variables"] == ["Name"]
    assert campaign["state"] == "draft"
    assert campaign["locked"] is False
    assert campaign["halt_reason"] is None


def test_create_normalizes_variables(db):
    service = CampaignService(db)

    campaign = service.create(
        name="Test",
        variables=[" Name ", "", "Name", "Email"],
    )

    assert campaign["variables"] == ["Name", "Email"]


def test_update_resets_preview_to_draft(db):
    service = CampaignService(db)

    campaign = service.create(name="Original")

    db.execute(
        "UPDATE campaigns SET state = 'previewed' WHERE id = ?",
        (campaign["id"],),
    )

    updated = service.update(
        campaign["id"],
        name="Updated",
        subject="New subject",
        body_html="<p>New body</p>",
        variables=["Name"],
    )

    assert updated["name"] == "Updated"
    assert updated["state"] == "draft"
    assert updated["variables"] == ["Name"]


def test_update_is_allowed_when_unlocked_and_finished(db):
    service = CampaignService(db)

    campaign = service.create(name="Original")

    db.execute(
        "UPDATE campaigns SET state = 'finished' WHERE id = ?",
        (campaign["id"],),
    )

    updated = service.update(
        campaign["id"],
        name="Updated",
        subject="Subject",
        body_html="Body",
        variables=[],
    )

    assert updated["state"] == "draft"


def test_locked_campaign_cannot_be_updated(db):
    service = CampaignService(db)

    campaign = service.create(name="Original")

    db.execute(
        "UPDATE campaigns SET locked = 1 WHERE id = ?",
        (campaign["id"],),
    )

    with pytest.raises(CampaignError) as exc_info:
        service.update(
            campaign["id"],
            name="Updated",
            subject="Subject",
            body_html="Body",
            variables=[],
        )

    assert exc_info.value.code == "campaign_locked"


def test_running_campaign_cannot_be_updated(db):
    service = CampaignService(db)

    campaign = service.create(name="Original")

    db.execute(
        "UPDATE campaigns SET state = 'running' WHERE id = ?",
        (campaign["id"],),
    )

    with pytest.raises(CampaignError) as exc_info:
        service.update(
            campaign["id"],
            name="Updated",
            subject="Subject",
            body_html="Body",
            variables=[],
        )

    assert exc_info.value.code == "campaign_running"


def test_missing_campaign_raises(db):
    service = CampaignService(db)

    with pytest.raises(CampaignError) as exc_info:
        service.get(999)

    assert exc_info.value.code == "campaign_not_found"


def test_duplicate_creates_new_draft(db):
    service = CampaignService(db)

    source = service.create(
        name="Original",
        subject="Subject",
        body_html="Body",
        variables=["Name"],
    )

    db.execute(
        "UPDATE campaigns SET state = 'finished', locked = 1 WHERE id = ?",
        (source["id"],),
    )

    duplicate = service.duplicate(
        source["id"],
        new_name="Copy",
    )

    assert duplicate["id"] != source["id"]
    assert duplicate["name"] == "Copy"
    assert duplicate["subject"] == "Subject"
    assert duplicate["body_html"] == "Body"
    assert duplicate["variables"] == ["Name"]
    assert duplicate["state"] == "draft"
    assert duplicate["locked"] is False


def test_duplicate_can_carry_recipients(db):
    service = CampaignService(db)

    source = service.create(name="Original")

    db.execute(
        "INSERT INTO recipients "
        "(campaign_id, email, values_json, status, attempts, position) "
        "VALUES (?, ?, ?, 'sent', 2, 0)",
        (source["id"], "person@example.com", '{"Name":"Prince"}'),
    )

    duplicate = service.duplicate(
        source["id"],
        new_name="Copy",
        carry_recipients=True,
    )

    row = db.execute(
        "SELECT email, values_json, status, attempts "
        "FROM recipients WHERE campaign_id = ?",
        (duplicate["id"],),
    ).fetchone()

    assert tuple(row) == (
        "person@example.com",
        '{"Name":"Prince"}',
        "pending",
        0,
    )


@pytest.mark.parametrize(
    "name",
    ["", "   ", "x" * 201],
)
def test_invalid_name_is_rejected(db, name):
    service = CampaignService(db)

    with pytest.raises(CampaignError) as exc_info:
        service.create(name=name)

    assert exc_info.value.code == "invalid_name"
