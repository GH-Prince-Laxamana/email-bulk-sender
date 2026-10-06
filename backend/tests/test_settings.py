import pytest

from app.providers.base import AuthenticationFailed
from app.services.settings import (
    SENDER_EMAIL_KEY,
    SENDER_PASSWORD_KEY,
    SettingsError,
    SettingsService,
)
from app.storage.secret_store import FileSecretStore


class FakeProvider:
    def __init__(self, username, password, *, timeout_seconds):
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds
        self.connected = False
        self.closed = False
        self.error = None

    def connect(self):
        if self.error:
            raise self.error
        self.connected = True

    def close(self):
        self.closed = True


class ProviderFactory:
    def __init__(self, error=None):
        self.error = error
        self.created = []

    def __call__(self, username, password, *, timeout_seconds):
        provider = FakeProvider(
            username,
            password,
            timeout_seconds=timeout_seconds,
        )
        provider.error = self.error
        self.created.append(provider)
        return provider


@pytest.fixture
def store(tmp_path):
    return FileSecretStore(tmp_path / "secrets.json")


def test_get_sender_settings_does_not_expose_password(store):
    store.set(SENDER_EMAIL_KEY, "sender@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "secret")

    service = SettingsService(store)

    settings = service.get_sender_settings()

    assert settings.email == "sender@gmail.com"
    assert settings.has_app_password is True
    assert not hasattr(settings, "app_password")


def test_save_sender_credentials_persists_both_values(store):
    service = SettingsService(store)

    settings = service.save_sender_credentials(
        " sender@gmail.com ",
        "app-password",
    )

    assert settings.email == "sender@gmail.com"
    assert settings.has_app_password is True
    assert store.get(SENDER_EMAIL_KEY) == "sender@gmail.com"
    assert store.get(SENDER_PASSWORD_KEY) == "app-password"


@pytest.mark.parametrize(
    ("email", "password", "code"),
    [
        ("", "secret", "invalid_email"),
        ("not-an-email", "secret", "invalid_email"),
        ("sender@gmail.com", "", "invalid_password"),
    ],
)
def test_save_rejects_invalid_credentials(store, email, password, code):
    service = SettingsService(store)

    with pytest.raises(SettingsError) as exc_info:
        service.save_sender_credentials(email, password)

    assert exc_info.value.code == code


def test_test_connection_uses_saved_credentials_only(store):
    store.set(SENDER_EMAIL_KEY, "sender@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "secret")

    factory = ProviderFactory()
    service = SettingsService(
        store,
        provider_factory=factory,
        test_timeout=4,
    )

    service.test_saved_connection()

    provider = factory.created[0]
    assert provider.username == "sender@gmail.com"
    assert provider.password == "secret"
    assert provider.timeout_seconds == 4
    assert provider.connected is True
    assert provider.closed is True


def test_test_connection_fails_when_credentials_are_missing(store):
    service = SettingsService(
        store,
        provider_factory=ProviderFactory(),
    )

    with pytest.raises(SettingsError) as exc_info:
        service.test_saved_connection()

    assert exc_info.value.code == "credentials_missing"


def test_test_connection_does_not_accept_or_use_unsaved_credentials(store):
    factory = ProviderFactory()
    service = SettingsService(
        store,
        provider_factory=factory,
    )

    with pytest.raises(SettingsError):
        service.test_saved_connection()

    assert factory.created == []


def test_test_connection_cooldown(store):
    store.set(SENDER_EMAIL_KEY, "sender@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "secret")

    now = [100.0]
    factory = ProviderFactory()

    service = SettingsService(
        store,
        provider_factory=factory,
        test_cooldown=15,
        clock=lambda: now[0],
    )

    service.test_saved_connection()
    assert len(factory.created) == 1

    now[0] = 110

    with pytest.raises(SettingsError) as exc_info:
        service.test_saved_connection()

    assert exc_info.value.code == "test_cooldown"
    assert exc_info.value.retry_after == pytest.approx(5)
    assert len(factory.created) == 1


def test_cooldown_applies_after_failed_connection(store):
    store.set(SENDER_EMAIL_KEY, "sender@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "secret")

    now = [100.0]
    factory = ProviderFactory(
        error=AuthenticationFailed("bad password"),
    )

    service = SettingsService(
        store,
        provider_factory=factory,
        test_cooldown=15,
        clock=lambda: now[0],
    )

    with pytest.raises(AuthenticationFailed):
        service.test_saved_connection()

    now[0] = 101

    with pytest.raises(SettingsError) as exc_info:
        service.test_saved_connection()

    assert exc_info.value.code == "test_cooldown"


def test_saving_new_credentials_resets_cooldown(store):
    store.set(SENDER_EMAIL_KEY, "old@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "old-secret")

    now = [100.0]
    factory = ProviderFactory()

    service = SettingsService(
        store,
        provider_factory=factory,
        test_cooldown=15,
        clock=lambda: now[0],
    )

    service.test_saved_connection()

    with pytest.raises(SettingsError):
        service.test_saved_connection()

    service.save_sender_credentials(
        "new@gmail.com",
        "new-secret",
    )

    service.test_saved_connection()

    assert len(factory.created) == 2
    assert factory.created[1].username == "new@gmail.com"


def test_provider_is_closed_when_connection_test_fails(store):
    store.set(SENDER_EMAIL_KEY, "sender@gmail.com")
    store.set(SENDER_PASSWORD_KEY, "secret")

    factory = ProviderFactory(
        error=AuthenticationFailed("bad password"),
    )

    service = SettingsService(
        store,
        provider_factory=factory,
    )

    with pytest.raises(AuthenticationFailed):
        service.test_saved_connection()

    assert factory.created[0].closed is True
