from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config import database_path
from app.services.settings import SettingsService, SENDER_EMAIL_KEY, SENDER_PASSWORD_KEY
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
    
    conn.execute(
        "INSERT INTO campaigns (name, subject, body_html, variables, state, locked, created_at, updated_at)"
        " VALUES ('Test', 'Hi', 'Hi', '[]', 'draft', 0, 'now', 'now')"
    )
    campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)

    client = TestClient(create_app(TOKEN, settings))

    yield client, path, campaign_id

def test_start_run_no_password(setup):
    client, _, campaign_id = setup
    # Campaign not in previewed state, but credentials are missing first
    response = client.post(f"/api/campaigns/{campaign_id}/run", headers=headers())
    assert response.status_code in (400, 409)
    error_code = response.json()["error"]["code"]
    assert error_code in ("credentials_missing", "campaign_not_ready")

def test_get_campaign_status(setup):
    client, _, campaign_id = setup
    response = client.get(f"/api/campaigns/{campaign_id}/status", headers=headers())
    assert response.status_code == 200

def test_stop_not_running(setup):
    client, _, campaign_id = setup
    response = client.post(f"/api/campaigns/{campaign_id}/stop", headers=headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run_not_active"
