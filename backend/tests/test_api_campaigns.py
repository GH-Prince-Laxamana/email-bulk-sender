from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config import database_path
from app.services.settings import SettingsService
from app.storage.db import connect
from app.storage.migrations import migrate
from app.storage.secret_store import FileSecretStore

TOKEN = "test-token"


def headers() -> dict[str, str]:
    return {
        "Host": "127.0.0.1",
        "X-App-Token": TOKEN,
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("BULKMAILER_DATA_DIR", str(tmp_path / "data"))

    path = database_path()
    conn = connect(path)
    migrate(conn, path)
    conn.close()

    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)

    client = TestClient(create_app(TOKEN, settings))

    yield client, path


def open_db(path) -> sqlite3.Connection:
    return connect(path)


def create_campaign(client, **overrides):
    payload = {
        "name": "Campaign 1",
        "subject": "Hello {{Name}}",
        "body_html": "<p>Hi {{Name|there}}</p>",
        "variables": ["Name"],
    }
    payload.update(overrides)

    return client.post(
        "/api/campaigns",
        headers=headers(),
        json=payload,
    )


def test_create_campaign(setup):
    client, path = setup

    response = create_campaign(client)

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Campaign 1"
    assert data["subject"] == "Hello {{Name}}"
    assert data["body_html"] == "<p>Hi {{Name|there}}</p>"
    assert data["variables"] == ["Name"]
    assert data["state"] == "draft"
    assert data["locked"] is False
    assert data["halt_reason"] is None


def test_list_campaigns(setup):
    client, _ = setup

    create_campaign(client, name="First")
    create_campaign(client, name="Second")

    response = client.get(
        "/api/campaigns",
        headers=headers(),
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "Second",
        "First",
    ]


def test_get_campaign(setup):
    client, _ = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    response = client.get(
        f"/api/campaigns/{campaign_id}",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()["id"] == campaign_id


def test_get_missing_campaign_returns_404(setup):
    client, _ = setup

    response = client.get(
        "/api/campaigns/999",
        headers=headers(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "campaign_not_found"


def test_update_resets_preview_to_draft(setup):
    client, path = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    conn = open_db(path)
    conn.execute(
        "UPDATE campaigns SET state = 'previewed' WHERE id = ?",
        (campaign_id,),
    )
    conn.close()

    response = client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers(),
        json={
            "name": "Updated",
            "subject": "New subject",
            "body_html": "<p>Updated</p>",
            "variables": ["First Name"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Updated"
    assert data["state"] == "draft"
    assert data["variables"] == ["First Name"]


def test_locked_campaign_returns_409(setup):
    client, path = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    conn = open_db(path)
    conn.execute(
        "UPDATE campaigns SET locked = 1 WHERE id = ?",
        (campaign_id,),
    )
    conn.close()

    response = client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers(),
        json={
            "name": "Updated",
            "subject": "Subject",
            "body_html": "Body",
            "variables": [],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "campaign_locked"


def test_running_campaign_returns_409(setup):
    client, path = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    conn = open_db(path)
    conn.execute(
        "UPDATE campaigns SET state = 'running' WHERE id = ?",
        (campaign_id,),
    )
    conn.close()

    response = client.patch(
        f"/api/campaigns/{campaign_id}",
        headers=headers(),
        json={
            "name": "Updated",
            "subject": "Subject",
            "body_html": "Body",
            "variables": [],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "campaign_running"


def test_duplicate_without_recipients(setup):
    client, path = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    response = client.post(
        f"/api/campaigns/{campaign_id}/duplicate",
        headers=headers(),
        json={
            "new_name": "Copy",
            "carry_recipients": False,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] != campaign_id
    assert data["name"] == "Copy"
    assert data["subject"] == "Hello {{Name}}"
    assert data["body_html"] == "<p>Hi {{Name|there}}</p>"
    assert data["variables"] == ["Name"]
    assert data["state"] == "draft"
    assert data["locked"] is False

    conn = open_db(path)
    count = conn.execute(
        "SELECT COUNT(*) FROM recipients WHERE campaign_id = ?",
        (data["id"],),
    ).fetchone()[0]
    conn.close()

    assert count == 0


def test_duplicate_carries_recipients_as_pending(setup):
    client, path = setup

    created = create_campaign(client)
    campaign_id = created.json()["id"]

    conn = open_db(path)
    conn.execute(
        "INSERT INTO recipients "
        "(campaign_id, email, values_json, status, attempts, position) "
        "VALUES (?, ?, ?, 'sent', 4, 0)",
        (
            campaign_id,
            "person@example.com",
            '{"Name":"Prince"}',
        ),
    )
    conn.close()

    response = client.post(
        f"/api/campaigns/{campaign_id}/duplicate",
        headers=headers(),
        json={
            "new_name": "Copy",
            "carry_recipients": True,
        },
    )

    assert response.status_code == 201
    new_id = response.json()["id"]

    conn = open_db(path)
    row = conn.execute(
        "SELECT email, values_json, status, attempts "
        "FROM recipients WHERE campaign_id = ?",
        (new_id,),
    ).fetchone()
    conn.close()

    assert tuple(row) == (
        "person@example.com",
        '{"Name":"Prince"}',
        "pending",
        0,
    )


def test_campaign_request_cannot_set_state_or_locked(setup):
    client, _ = setup

    response = client.post(
        "/api/campaigns",
        headers=headers(),
        json={
            "name": "Campaign",
            "subject": "Subject",
            "body_html": "Body",
            "variables": [],
            "state": "previewed",
            "locked": True,
        },
    )

    assert response.status_code == 422
