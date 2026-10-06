from __future__ import annotations

import logging
import random
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from ..providers.base import DeliveryUncertain, MailProvider, ProviderError
from ..storage import repo
from ..storage.db import connect
from .builder import AttachmentRule, BuildError, Content, Recipient, build_message

log = logging.getLogger(__name__)


def error_code(err: Exception) -> str:
    """RecipientRejected -> 'recipient_rejected'."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", type(err).__name__).lower()


@dataclass(frozen=True)
class RunResult:
    state: str  # 'finished' | 'paused' | 'draft'
    reason: str | None = None


class CampaignRunner:
    """Runs one campaign to completion, pause, or halt. Call from one thread.

    The campaign must already be claimed (state 'running') via repo.claim_run.
    """

    def __init__(
        self,
        db_path: str | Path,
        provider: MailProvider,
        sender: str,
        *,
        delay_range: tuple[float, float] = (1.0, 3.0),
        max_retries: int = 2,
        retry_backoff: float = 5.0,
    ) -> None:
        self._db_path = db_path
        self._provider = provider
        self._sender = sender
        self._delay_range = delay_range
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff

    def run(self, campaign_id: int, stop: threading.Event) -> RunResult:
        conn = connect(self._db_path)  # each thread owns its connection
        try:
            return self._run(conn, campaign_id, stop)
        finally:
            self._provider.close()
            conn.close()

    def _run(self, conn, campaign_id: int, stop: threading.Event) -> RunResult:
        campaign = repo.get_campaign(conn, campaign_id)
        if campaign is None or campaign.state != "running":
            raise RuntimeError(
                "Campaign must be claimed (state 'running') before it is run"
            )

        content = Content(campaign.subject, campaign.body_html)
        rules = [
            AttachmentRule(r["path"], r["folder"], r["filename_template"])
            for r in repo.get_attachment_rules(conn, campaign_id)
        ]

        problem = self._preflight(conn, campaign_id, content, rules)
        if problem:
            return self._finish(conn, campaign_id, "draft", problem)
        try:
            self._provider.connect()
        except ProviderError as err:
            return self._finish(conn, campaign_id, "paused", str(err))

        current: int | None = None  # recipient currently in 'sending'
        try:
            while True:
                if stop.is_set():
                    return self._finish(conn, campaign_id, "paused", None)
                recipient = repo.next_pending(conn, campaign_id)
                if recipient is None:
                    return self._finish(conn, campaign_id, "finished", None)

                try:
                    message = build_message(
                        self._sender,
                        content,
                        rules,
                        Recipient(recipient.email, recipient.values),
                    )
                except BuildError as err:
                    repo.mark_failed(conn, recipient.id, err.code, str(err))
                    continue

                repo.mark_sending(conn, recipient.id)
                current = recipient.id
                try:
                    self._send_with_retries(message, stop)
                except ProviderError as err:
                    if err.halts_run:
                        repo.mark_pending(conn, recipient.id)  # definitely not sent
                        current = None
                        return self._finish(conn, campaign_id, "paused", str(err))
                    if isinstance(err, DeliveryUncertain):
                        repo.mark_interrupted(
                            conn, recipient.id, error_code(err), str(err)
                        )
                    else:
                        repo.mark_failed(conn, recipient.id, error_code(err), str(err))
                else:
                    repo.mark_sent(conn, recipient.id)
                current = None

                if repo.has_pending(conn, campaign_id):
                    stop.wait(random.uniform(*self._delay_range))
        except (
            Exception
        ) as exc:  # a bug must never leave the campaign stuck on 'running'
            log.exception("Unexpected error during campaign run")
            reason = f"Unexpected error: {exc}"
            if current is not None:
                repo.mark_interrupted(conn, current, "unexpected_error", reason)
            return self._finish(conn, campaign_id, "paused", reason)

    def _preflight(self, conn, campaign_id: int, content, rules) -> str | None:
        problems = []
        for recipient in repo.pending_recipients(conn, campaign_id):
            try:
                build_message(
                    self._sender,
                    content,
                    rules,
                    Recipient(recipient.email, recipient.values),
                    attach_files=False,
                )
            except BuildError as err:
                problems.append(f"{recipient.email}: {err}")
        if problems:
            return (
                f"{len(problems)} recipient(s) can no longer be built "
                f"(first: {problems[0]}). Run the preview again."
            )
        return None

    def _send_with_retries(self, message, stop: threading.Event) -> None:
        attempt = 0
        while True:
            try:
                self._provider.send(message)
                return
            except ProviderError as err:
                if err.retryable and attempt < self._max_retries and not stop.is_set():
                    attempt += 1
                    stop.wait(self._retry_backoff * attempt)
                    continue
                raise

    @staticmethod
    def _finish(conn, campaign_id: int, state: str, reason: str | None) -> RunResult:
        repo.set_state(conn, campaign_id, state, reason)
        return RunResult(state, reason)
