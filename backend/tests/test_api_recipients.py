from __future__ import annotations

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
    return {"Host": "127.0.0.1", "X-App-Token": TOKEN}

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("BULKMAILER_DATA_DIR", str(tmp_path / "data"))

    path = database_path()
    conn = connect(path)
    migrate(conn, path)
    
    conn.execute("INSERT INTO campaigns (name, subject, body_html, variables, state, locked, created_at, updated_at) VALUES ('Test', 'Hi', 'Hi', '[]', 'draft', 0, 'now', 'now')")
    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)

    client = TestClient(create_app(TOKEN, settings))

    yield client, path, campaign_id

def test_list_recipients(setup):
    client, _, campaign_id = setup
    response = client.get(f"/api/campaigns/{campaign_id}/recipients", headers=headers())
    assert response.status_code == 200
    assert response.json() == []

def test_create_recipient(setup):
    client, _, campaign_id = setup
    payload = {"email": "alice@example.com", "values": {"name": "Alice"}}
    response = client.post(
        f"/api/campaigns/{campaign_id}/recipients",
        json=payload,
        headers=headers()
    )
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"

def test_import_recipients_csv(setup):
    client, _, campaign_id = setup
    payload = {"text": "email,name\nbob@example.com,Bob\n"}
    response = client.post(
        f"/api/campaigns/{campaign_id}/recipients/import",
        json=payload,
        headers=headers()
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == 1
