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
    conn.close()

    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)

    client = TestClient(create_app(TOKEN, settings))

    yield client, path

def test_post_test_send(setup):
    client, _ = setup
    response = client.post(
        "/api/settings/sender/test-send",
        headers=headers()
    )
    # Should fail due to no credentials, but the route exists and processes
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "credentials_missing"
