from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Callable

from .base import (
    AuthenticationFailed,
    ConnectionLost,
    DeliveryUncertain,
    LimitReached,
    ProviderError,
    RecipientRejected,
    SenderRejected,
    TemporaryFailure,
)

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 465
TIMEOUT_SECONDS = 30
_LIMIT_HINTS = ("5.4.5", "daily user sending", "quota", "sending limit")


def _text(raw: Any) -> str:
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def _looks_like_limit(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _LIMIT_HINTS)


def translate(exc: BaseException) -> ProviderError:
    """Map a smtplib/socket exception to a provider error. Pure, no I/O."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return AuthenticationFailed(
            "Gmail rejected the login. Check the address and app password, "
            "and that 2-Step Verification is on."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        code, reason = next(iter(exc.recipients.values()), (550, b""))
        message = f"Recipient refused ({code}): {_text(reason)}"
        if 400 <= code < 500:
            return TemporaryFailure(message)
        return RecipientRejected(message)
    if isinstance(exc, smtplib.SMTPSenderRefused):
        text = _text(exc.smtp_error)
        if _looks_like_limit(text):
            return LimitReached(f"Gmail sending limit reached: {text}")
        return SenderRejected(f"Sender refused ({exc.smtp_code}): {text}")
    if isinstance(exc, smtplib.SMTPDataError):
        text = _text(exc.smtp_error)
        if _looks_like_limit(text):
            return LimitReached(f"Gmail sending limit reached: {text}")
        if 400 <= exc.smtp_code < 500:
            return TemporaryFailure(f"Temporary error ({exc.smtp_code}): {text}")
        return RecipientRejected(f"Message rejected ({exc.smtp_code}): {text}")
    if isinstance(
        exc,
        (smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError, ssl.SSLError),
    ):
        return DeliveryUncertain(f"Connection problem during send: {exc}")
    return ProviderError(str(exc))


class GmailSmtpProvider:
    def __init__(
        self,
        username: str,
        app_password: str,
        *,
        smtp_factory: Callable[[], Any] | None = None,
        timeout_seconds: float = TIMEOUT_SECONDS,
    ) -> None:
        self._username = username
        self._password = app_password
        self._timeout_seconds = timeout_seconds
        self._factory = smtp_factory or self._default_factory
        self._server: Any = None

    def _default_factory(self) -> smtplib.SMTP_SSL:
        return smtplib.SMTP_SSL(
            GMAIL_HOST,
            GMAIL_PORT,
            timeout=self._timeout_seconds,
            context=ssl.create_default_context(),
        )

    @staticmethod
    def _discard(server: Any) -> None:
        if server is not None:
            try:
                server.close()
            except Exception:
                pass

    def connect(self) -> None:
        self.close()
        server = None
        try:
            server = self._factory()
            server.login(self._username, self._password)
        except smtplib.SMTPAuthenticationError as exc:
            self._discard(server)
            raise translate(exc) from exc
        except (smtplib.SMTPException, OSError) as exc:
            self._discard(server)
            raise ConnectionLost(f"Could not connect to Gmail: {exc}") from exc
        self._server = server

    def _alive(self) -> bool:
        try:
            return self._server.noop()[0] == 250
        except (smtplib.SMTPException, OSError):
            return False

    def send(self, message: EmailMessage) -> None:
        # Checking *before* sending is safe. Retrying *after* a failed send is not.
        if self._server is None or not self._alive():
            self.connect()
        try:
            assert self._server is not None
            self._server.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            error = translate(exc)
            if isinstance(error, DeliveryUncertain):
                self._discard(self._server)
                self._server = None  # the next send reconnects first
            raise error from exc

    def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            try:
                server.quit()
            except (smtplib.SMTPException, OSError):
                self._discard(server)
