from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol


class ProviderError(Exception):
    halts_run = False  # True: stop the whole campaign
    retryable = False  # True: worth an automatic retry for this recipient


class AuthenticationFailed(ProviderError):
    halts_run = True


class LimitReached(ProviderError):
    halts_run = True


class ConnectionLost(ProviderError):
    halts_run = True


class SenderRejected(ProviderError):
    halts_run = True


class RecipientRejected(ProviderError):
    """Permanent failure for this recipient only."""


class TemporaryFailure(ProviderError):
    retryable = True


class DeliveryUncertain(ProviderError):
    """The message may or may not have been delivered. Never auto-retry."""


class MailProvider(Protocol):
    def connect(self) -> None: ...

    def send(self, message: EmailMessage) -> None: ...

    def close(self) -> None: ...
