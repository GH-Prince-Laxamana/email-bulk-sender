from __future__ import annotations

from email.message import EmailMessage
from typing import Callable

from app.providers.gmail import GmailSmtpProvider
from app.providers.base import ProviderError
from app.services.settings import (
    SENDER_PASSWORD_KEY,
    SettingsService,
)
from app.storage.secret_store import SecretStore


class TestSendError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TestSendService:
    def __init__(
        self,
        settings_service: SettingsService,
        secret_store: SecretStore,
        *,
        provider_factory: Callable[..., GmailSmtpProvider] = GmailSmtpProvider,
    ) -> None:
        self._settings = settings_service
        self._secrets = secret_store
        self._provider_factory = provider_factory

    def send_to_self(self) -> None:
        settings = self._settings.get_sender_settings()
        sender = settings.email
        password = self._secrets.get(SENDER_PASSWORD_KEY)

        if not sender or not password:
            raise TestSendError(
                "credentials_missing",
                "Saved sender credentials are incomplete.",
            )

        message = EmailMessage()
        message["From"] = sender
        message["To"] = sender
        message["Subject"] = "BulkMailer test email"
        message.set_content(
            "This is a test email from BulkMailer.\n\n"
            "Your saved Gmail sender credentials are working.",
        )

        provider = self._provider_factory(
            sender,
            password,
        )

        try:
            provider.connect()
            provider.send(message)
        except ProviderError:
            raise
        finally:
            provider.close()
