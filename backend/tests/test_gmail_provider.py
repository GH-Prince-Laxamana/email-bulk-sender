import smtplib
from email.message import EmailMessage

import pytest

from app.providers.base import (
    AuthenticationFailed,
    DeliveryUncertain,
    LimitReached,
    RecipientRejected,
    SenderRejected,
    TemporaryFailure,
)
from app.providers.gmail import GmailSmtpProvider, translate

TRANSLATIONS = [
    (smtplib.SMTPAuthenticationError(535, b"5.7.8 not accepted"), AuthenticationFailed),
    (
        smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"5.1.1 no such user")}),
        RecipientRejected,
    ),
    (
        smtplib.SMTPRecipientsRefused({"a@x.com": (450, b"4.2.1 try later")}),
        TemporaryFailure,
    ),
    (
        smtplib.SMTPSenderRefused(
            550, b"5.4.5 Daily user sending quota exceeded", "o@g.com"
        ),
        LimitReached,
    ),
    (smtplib.SMTPSenderRefused(550, b"5.7.1 not allowed", "o@g.com"), SenderRejected),
    (
        smtplib.SMTPDataError(550, b"5.4.5 Daily user sending quota exceeded"),
        LimitReached,
    ),
    (smtplib.SMTPDataError(552, b"5.3.4 message too large"), RecipientRejected),
    (smtplib.SMTPDataError(451, b"4.3.0 temporary problem"), TemporaryFailure),
    (smtplib.SMTPServerDisconnected("closed"), DeliveryUncertain),
    (TimeoutError(), DeliveryUncertain),
]


@pytest.mark.parametrize("exc,expected", TRANSLATIONS)
def test_translate(exc, expected):
    assert type(translate(exc)) is expected


class FakeSMTP:
    def __init__(self, login_error=None, send_error=None):
        self.login_error = login_error
        self.send_error = send_error
        self.noop_ok = True
        self.sent = []

    def login(self, user, password):
        if self.login_error:
            raise self.login_error

    def noop(self):
        if not self.noop_ok:
            raise smtplib.SMTPServerDisconnected("gone")
        return (250, b"OK")

    def send_message(self, msg):
        if self.send_error:
            raise self.send_error
        self.sent.append(msg)

    def quit(self):
        pass

    def close(self):
        pass


def provider_with(*servers):
    queue = list(servers)
    calls = []

    def factory():
        calls.append(1)
        return queue.pop(0)

    return GmailSmtpProvider("org@gmail.com", "app-pass", smtp_factory=factory), calls


def message(to="ana@example.com"):
    msg = EmailMessage()
    msg["To"] = to
    msg.set_content("hi")
    return msg


def test_bad_login_raises_authentication_failed():
    bad = FakeSMTP(login_error=smtplib.SMTPAuthenticationError(535, b"nope"))
    provider, _ = provider_with(bad)
    with pytest.raises(AuthenticationFailed):
        provider.connect()


def test_send_reuses_one_connection():
    server = FakeSMTP()
    provider, calls = provider_with(server)
    provider.connect()
    provider.send(message("a@example.com"))
    provider.send(message("b@example.com"))
    assert len(server.sent) == 2
    assert len(calls) == 1


def test_dead_connection_is_replaced_before_sending():
    first, second = FakeSMTP(), FakeSMTP()
    provider, _ = provider_with(first, second)
    provider.connect()
    first.noop_ok = False
    provider.send(message())
    assert first.sent == []
    assert len(second.sent) == 1


def test_disconnect_during_send_is_uncertain_and_not_retried():
    first = FakeSMTP(send_error=smtplib.SMTPServerDisconnected("dropped"))
    second = FakeSMTP()
    provider, _ = provider_with(first, second)
    provider.connect()
    with pytest.raises(DeliveryUncertain):
        provider.send(message("ana@example.com"))
    assert first.sent == [] and second.sent == []  # no automatic resend
    provider.send(message("ben@example.com"))  # next send reconnects
    assert [m["To"] for m in second.sent] == ["ben@example.com"]


def test_recipient_refusal_keeps_the_connection():
    server = FakeSMTP(
        send_error=smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"no such user")})
    )
    provider, calls = provider_with(server)
    provider.connect()
    with pytest.raises(RecipientRejected):
        provider.send(message("a@x.com"))
    server.send_error = None
    provider.send(message("b@x.com"))
    assert len(server.sent) == 1
    assert len(calls) == 1
