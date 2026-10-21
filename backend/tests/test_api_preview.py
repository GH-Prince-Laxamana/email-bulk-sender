from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config import database_path
from app.services.settings import SettingsService, SENDER_EMAIL_KEY
from app.storage.db import connect
from app.storage.migrations import migrate
from app.storage.secret_store import FileSecretStore
from app.storage import repo

TOKEN = "test-token"

def headers() -> dict[str, str]:
    return {"Host": "127.0.0.1", "X-App-Token": TOKEN}

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("BULKMAILER_DATA_DIR", str(tmp_path / "data"))

    path = database_path()
    conn = connect(path)
    migrate(conn, path)
    
    conn.execute(
        "INSERT INTO campaigns (name, subject, body_html, variables, state, locked, created_at, updated_at)"
        " VALUES ('Test', 'Hi', 'Hi', '[]', 'draft', 0, 'now', 'now')"
    )
    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO recipients (campaign_id, email, values_json, status, attempts, position)"
        " VALUES (?, 'test@example.com', '{}', 'pending', 0, 0)",
        (campaign_id,)
    )
    conn.close()

    secrets = FileSecretStore(tmp_path / "secrets.json")
    secrets.set(SENDER_EMAIL_KEY, "sender@example.com")
    settings = SettingsService(secrets)

    client = TestClient(create_app(TOKEN, settings))

    yield client, path, campaign_id

def test_get_preview(setup):
    client, _, campaign_id = setup
    response = client.post(f"/api/campaigns/{campaign_id}/preview", headers=headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["valid"] == 1
    assert body["clean"] is True
    assert body["previews"][0]["attachments"] == []


def test_recipient_files_match_send_rules(setup, tmp_path):
    client, path, campaign_id = setup
    shared = tmp_path / "guide.txt"
    shared.write_bytes(b"Shared guide")
    for name in ("Alice", "Bob"):
        (tmp_path / f"{name}.txt").write_bytes(name.encode())
    conn = connect(path)
    conn.execute("UPDATE recipients SET values_json = ?", ('{"name":"Alice"}',))
    repo.insert_recipients(conn, campaign_id, [("bob@example.com", {"name": "Bob"})])
    repo.replace_attachment_rules(conn, campaign_id, [
        {"path": str(shared), "folder": None, "filename_template": None},
        {"path": None, "folder": str(tmp_path), "filename_template": "{{name}}.txt"},
    ])
    recipients = repo.list_recipients(conn, campaign_id)
    other_campaign = repo.create_campaign(conn, name="Other", subject="Hi", body_html="Hi", variables=[])
    conn.close()

    campaign_preview = client.post(f"/api/campaigns/{campaign_id}/preview", headers=headers()).json()
    for recipient, name in zip(recipients, ("Alice", "Bob")):
        base = f"/api/campaigns/{campaign_id}/recipients/{recipient.id}"
        response = client.post(f"{base}/preview", headers=headers())
        assert response.status_code == 200
        attachments = response.json()["attachments"]
        assert attachments == [
            {"filename": "guide.txt", "path": str(shared.resolve()), "size": 12},
            {"filename": f"{name}.txt", "path": str((tmp_path / f"{name}.txt").resolve()), "size": len(name)},
        ]
        assert next(p for p in campaign_preview["previews"] if p["recipient_id"] == recipient.id)["attachments"] == attachments
        file_response = client.get(f"{base}/attachments/1", headers=headers())
        assert file_response.status_code == 200
        assert file_response.content == name.encode()
        assert file_response.headers["cache-control"] == "no-store"
        assert client.get(f"{base}/attachments/1", headers={"Host": "127.0.0.1"}).status_code == 401
        for index in (-1, 2):
            assert client.get(f"{base}/attachments/{index}", headers=headers()).status_code == 404
        assert client.get(f"/api/campaigns/{other_campaign}/recipients/{recipient.id}/attachments/0", headers=headers()).status_code == 404

    (tmp_path / "Alice.txt").unlink()
    base = f"/api/campaigns/{campaign_id}/recipients/{recipients[0].id}"
    missing = client.get(f"{base}/attachments/1", headers=headers())
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "attachment_missing"


def test_attachment_preview_rejects_unsafe_filename(setup, tmp_path):
    client, path, campaign_id = setup
    conn = connect(path)
    conn.execute("UPDATE recipients SET values_json = ?", ('{"name":"../private"}',))
    repo.replace_attachment_rules(conn, campaign_id, [
        {"path": None, "folder": str(tmp_path), "filename_template": "{{name}}.txt"},
    ])
    recipient = repo.list_recipients(conn, campaign_id)[0]
    conn.close()
    response = client.get(f"/api/campaigns/{campaign_id}/recipients/{recipient.id}/attachments/0", headers=headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "attachment_unsafe"
