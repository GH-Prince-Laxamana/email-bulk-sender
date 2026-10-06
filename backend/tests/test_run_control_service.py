from __future__ import annotations

import pytest
from pathlib import Path

from app.services.run_control import RunControlService, RunControlError
from app.services.settings import SettingsService, SENDER_EMAIL_KEY, SENDER_PASSWORD_KEY
from app.storage.secret_store import FileSecretStore
from app.storage import repo
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.fakes import FakeProvider

@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = connect(path)
    migrate(conn, path)

    campaign_id = repo.create_campaign(
        conn,
        name="Test Campaign",
        subject="Hello",
        body_html="<p>Hi</p>"
    )

    yield path, conn, campaign_id
    conn.close()

def test_run_control_missing_credentials(db, tmp_path):
    db_path, conn, campaign_id = db
    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)
    
    service = RunControlService(
        db_path=db_path,
        settings_service=settings,
        secret_store=secrets,
        provider_factory=lambda *args, **kwargs: FakeProvider()
    )

    with pytest.raises(RunControlError) as exc_info:
        service.start(campaign_id)
        
    assert exc_info.value.code == "credentials_missing"

def test_run_control_start_and_stop(db, tmp_path):
    db_path, conn, campaign_id = db
    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)
    
    secrets.set(SENDER_EMAIL_KEY, "test@example.com")
    secrets.set(SENDER_PASSWORD_KEY, "password")

    service = RunControlService(
        db_path=db_path,
        settings_service=settings,
        secret_store=secrets,
        provider_factory=lambda *args, **kwargs: FakeProvider()
    )
    
    conn.execute("UPDATE campaigns SET state = 'previewed' WHERE id = ?", (campaign_id,))
    conn.commit()

    status = service.start(campaign_id)
    assert status["campaign_id"] == campaign_id
    assert status["state"] == "running"

    # stop() returns None on success; it signals the thread
    service.stop(campaign_id)
