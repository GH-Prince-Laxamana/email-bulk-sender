from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from app.providers.gmail import GmailSmtpProvider
from app.storage.secret_store import SecretStore

SENDER_EMAIL_KEY = "sender_email"
SENDER_PASSWORD_KEY = "sender_app_password"

DEFAULT_TEST_TIMEOUT = 5.0
DEFAULT_TEST_COOLDOWN = 15.0


class SettingsError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class SenderSettings:
    email: str | None
    has_app_password: bool


class SettingsService:
    def __init__(
        self,
        secret_store: SecretStore,
        *,
        provider_factory: Callable[..., GmailSmtpProvider] | None = None,
        test_timeout: float = DEFAULT_TEST_TIMEOUT,
        test_cooldown: float = DEFAULT_TEST_COOLDOWN,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._secrets = secret_store
        self._provider_factory = provider_factory or GmailSmtpProvider
        self._test_timeout = test_timeout
        self._test_cooldown = test_cooldown
        self._clock = clock
        self._last_test_at: float | None = None

    def get_sender_settings(self) -> SenderSettings:
        email = self._secrets.get(SENDER_EMAIL_KEY)
        password = self._secrets.get(SENDER_PASSWORD_KEY)

        return SenderSettings(
            email=email,
            has_app_password=bool(password),
        )

    def save_sender_credentials(
        self,
        email: str,
        app_password: str,
    ) -> SenderSettings:
        email = email.strip()

        if not email:
            raise SettingsError(
                "invalid_email",
                "Sender email is required.",
            )

        if "@" not in email:
            raise SettingsError(
                "invalid_email",
                "Sender email is invalid.",
            )

        if not app_password:
            raise SettingsError(
                "invalid_password",
                "App password is required.",
            )

        self._secrets.set(SENDER_EMAIL_KEY, email)
        self._secrets.set(SENDER_PASSWORD_KEY, app_password)

        # New credentials should allow an immediate test.
        self._last_test_at = None

        return self.get_sender_settings()

    def test_saved_connection(self) -> None:
        now = self._clock()

        if self._last_test_at is not None:
            elapsed = now - self._last_test_at
            if elapsed < self._test_cooldown:
                raise SettingsError(
                    "test_cooldown",
                    "Connection test is temporarily unavailable.",
                    retry_after=self._test_cooldown - elapsed,
                )

        email = self._secrets.get(SENDER_EMAIL_KEY)
        password = self._secrets.get(SENDER_PASSWORD_KEY)

        if not email or not password:
            raise SettingsError(
                "credentials_missing",
                "Saved sender credentials are incomplete.",
            )

        # Start the cooldown before touching the network so repeated failures
        # cannot be used to hammer the SMTP server.
        self._last_test_at = now

        provider = self._provider_factory(
            email,
            password,
            timeout_seconds=self._test_timeout,
        )

        try:
            provider.connect()
        finally:
            provider.close()
