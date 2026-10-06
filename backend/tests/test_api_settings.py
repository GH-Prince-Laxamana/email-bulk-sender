from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.providers.base import AuthenticationFailed
from app.services.settings import SettingsService
from app.storage.secret_store import FileSecretStore

TOKEN = "test-token"


class FakeProvider:
    def __init__(self, username, password, *, timeout_seconds):
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds
        self.closed = False
        self.error = None

    def connect(self):
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


@pytest.fixture
def setup(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")

    class Factory:
        def __init__(self):
            self.created = []

        def __call__(self, username, password, *, timeout_seconds):
            provider = FakeProvider(
                username,
                password,
                timeout_seconds=timeout_seconds,
            )
            self.created.append(provider)
            return provider

    factory = Factory()

    service = SettingsService(
        store,
        provider_factory=factory,
        test_timeout=4,
        test_cooldown=15,
    )

    app = create_app(TOKEN, service)
    client = TestClient(app)

    return client, store, factory, service


def headers():
    return {
        "Host": "127.0.0.1",
        "X-App-Token": TOKEN,
    }


def test_get_sender_settings(setup):
    client, store, _, _ = setup
    store.set("sender_email", "sender@gmail.com")
    store.set("sender_app_password", "secret")

    response = client.get(
        "/api/settings/sender",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": "sender@gmail.com",
        "has_app_password": True,
    }
    assert "secret" not in response.text


def test_save_sender_settings(setup):
    client, store, _, _ = setup

    response = client.put(
        "/api/settings/sender",
        headers=headers(),
        json={
            "email": " sender@gmail.com ",
            "app_password": "secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": "sender@gmail.com",
        "has_app_password": True,
    }
    assert store.get("sender_email") == "sender@gmail.com"
    assert store.get("sender_app_password") == "secret"
    assert "secret" not in response.text


def test_save_rejects_invalid_sender(setup):
    client, _, _, _ = setup

    response = client.put(
        "/api/settings/sender",
        headers=headers(),
        json={
            "email": "not-an-email",
            "app_password": "secret",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_email"


def test_test_connection_uses_saved_credentials(setup):
    client, store, factory, _ = setup
    store.set("sender_email", "sender@gmail.com")
    store.set("sender_app_password", "secret")

    response = client.post(
        "/api/settings/sender/test",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    provider = factory.created[0]
    assert provider.username == "sender@gmail.com"
    assert provider.password == "secret"
    assert provider.timeout_seconds == 4
    assert provider.closed is True


def test_test_connection_does_not_accept_credentials_from_request(setup):
    client, store, factory, _ = setup
    store.set("sender_email", "saved@gmail.com")
    store.set("sender_app_password", "saved-secret")

    response = client.post(
        "/api/settings/sender/test",
        headers=headers(),
        json={
            "email": "attacker@gmail.com",
            "app_password": "attacker-secret",
        },
    )

    assert response.status_code == 200

    provider = factory.created[0]
    assert provider.username == "saved@gmail.com"
    assert provider.password == "saved-secret"


def test_test_connection_requires_saved_credentials(setup):
    client, _, factory, _ = setup

    response = client.post(
        "/api/settings/sender/test",
        headers=headers(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "credentials_missing"
    assert factory.created == []


def test_test_connection_auth_failure_returns_provider_error(setup):
    client, store, factory, _ = setup
    store.set("sender_email", "sender@gmail.com")
    store.set("sender_app_password", "secret")

    factory.created.clear()

    original_call = factory.__call__

    def failing_factory(username, password, *, timeout_seconds):
        provider = original_call(
            username,
            password,
            timeout_seconds=timeout_seconds,
        )
        provider.error = AuthenticationFailed("bad password")
        return provider

    # Replace the service factory for this test.
    service = SettingsService(
        store,
        provider_factory=failing_factory,
        test_timeout=4,
        test_cooldown=15,
    )
    client = TestClient(create_app(TOKEN, service))

    response = client.post(
        "/api/settings/sender/test",
        headers=headers(),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "authentication_failed"
    assert "bad password" in response.json()["error"]["message"]


def test_test_connection_cooldown_returns_429(setup):
    client, store, _, _ = setup
    store.set("sender_email", "sender@gmail.com")
    store.set("sender_app_password", "secret")

    first = client.post(
        "/api/settings/sender/test",
        headers=headers(),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/settings/sender/test",
        headers=headers(),
    )

    assert second.status_code == 429
    assert second.json()["error"]["code"] == "test_cooldown"
    assert "Retry-After" in second.headers
