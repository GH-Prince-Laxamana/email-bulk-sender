from __future__ import annotations

import pytest
from pathlib import Path

from app.services.send_test import TestSendService, TestSendError
from app.services.settings import SettingsService, SENDER_EMAIL_KEY, SENDER_PASSWORD_KEY
from app.storage.secret_store import FileSecretStore
from tests.fakes import FakeProvider

def test_send_test_missing_credentials(tmp_path):
    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)
    
    service = TestSendService(
        settings,
        secrets,
        provider_factory=lambda *args, **kwargs: FakeProvider()
    )

    with pytest.raises(TestSendError) as exc_info:
        service.send_to_self()
        
    assert exc_info.value.code == "credentials_missing"

def test_send_test_success(tmp_path):
    secrets = FileSecretStore(tmp_path / "secrets.json")
    settings = SettingsService(secrets)
    
    secrets.set(SENDER_EMAIL_KEY, "test@example.com")
    secrets.set(SENDER_PASSWORD_KEY, "password")
    
    provider = FakeProvider()

    service = TestSendService(
        settings,
        secrets,
        provider_factory=lambda *args, **kwargs: provider
    )

    service.send_to_self()
    assert len(provider.sent) == 1
    assert provider.sent[0]["To"] == "test@example.com"
