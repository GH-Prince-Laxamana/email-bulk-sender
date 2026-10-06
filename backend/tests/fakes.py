from __future__ import annotations

from email.message import EmailMessage


class FakeProvider:
    """Scripted provider for engine tests.

    outcomes: {"to@address": [exception_or_None, ...]} consumed one per send
    attempt to that address; None (or an exhausted list) means success.
    """

    def __init__(self, outcomes=None, connect_error=None):
        self.outcomes = {to: list(items) for to, items in (outcomes or {}).items()}
        self.connect_error = connect_error
        self.sent: list[EmailMessage] = []
        self.connects = 0
        self.closes = 0

    def connect(self) -> None:
        self.connects += 1
        if self.connect_error:
            raise self.connect_error

    def send(self, message: EmailMessage) -> None:
        queue = self.outcomes.get(message["To"], [])
        outcome = queue.pop(0) if queue else None
        if outcome is not None:
            raise outcome
        self.sent.append(message)

    def close(self) -> None:
        self.closes += 1
