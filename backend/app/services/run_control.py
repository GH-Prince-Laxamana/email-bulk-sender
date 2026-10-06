from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.mail_core.engine import CampaignRunner, RunResult
from app.providers.gmail import GmailSmtpProvider
from app.services.settings import (
    SENDER_PASSWORD_KEY,
    SettingsService,
)
from app.storage import repo
from app.storage.db import connect
from app.storage.secret_store import SecretStore

DEFAULT_DAILY_CAP = 500


class RunControlError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RunControlService:
    def __init__(
        self,
        db_path: str | Path,
        settings_service: SettingsService,
        secret_store: SecretStore,
        *,
        provider_factory: Callable[..., GmailSmtpProvider] = GmailSmtpProvider,
        runner_factory: Callable[..., CampaignRunner] = CampaignRunner,
        daily_cap: int = DEFAULT_DAILY_CAP,
    ) -> None:
        self._db_path = Path(db_path)
        self._settings = settings_service
        self._secrets = secret_store
        self._provider_factory = provider_factory
        self._runner_factory = runner_factory
        self._daily_cap = daily_cap

        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop: threading.Event | None = None
        self._campaign_id: int | None = None
        self._last_results: dict[int, RunResult] = {}

    def start(self, campaign_id: int) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RunControlError(
                    "run_active",
                    "A campaign is already running.",
                )

            settings = self._settings.get_sender_settings()
            sender = settings.email
            password = self._secrets.get(SENDER_PASSWORD_KEY)

            if not sender or not password:
                raise RunControlError(
                    "credentials_missing",
                    "Saved sender credentials are incomplete.",
                )

            conn = connect(self._db_path)
            try:
                campaign = repo.get_campaign(conn, campaign_id)

                if campaign is None:
                    raise RunControlError(
                        "campaign_not_found",
                        "Campaign not found.",
                    )

                if campaign.state not in {"previewed", "paused"}:
                    raise RunControlError(
                        "campaign_not_ready",
                        "Campaign must have a clean preview before it can run.",
                    )

                warning = self._daily_cap_warning(
                    conn,
                    campaign_id,
                )

                provider = self._provider_factory(
                    sender,
                    password,
                )

                if not repo.claim_run(conn, campaign_id):
                    raise RunControlError(
                        "run_active",
                        "A campaign is already running.",
                    )
            finally:
                conn.close()

            stop = threading.Event()

            thread = threading.Thread(
                target=self._worker,
                args=(campaign_id, sender, provider, stop),
                name=f"campaign-runner-{campaign_id}",
                daemon=True,
            )

            self._thread = thread
            self._stop = stop
            self._campaign_id = campaign_id

            thread.start()

            return {
                "campaign_id": campaign_id,
                "state": "running",
                "daily_cap_warning": warning,
            }

    def stop(self, campaign_id: int) -> None:
        with self._lock:
            if (
                self._thread is None
                or not self._thread.is_alive()
                or self._campaign_id != campaign_id
                or self._stop is None
            ):
                raise RunControlError(
                    "run_not_active",
                    "This campaign is not currently running.",
                )

            self._stop.set()

    def status(self, campaign_id: int) -> dict[str, Any]:
        conn = connect(self._db_path)
        try:
            campaign = repo.get_campaign(
                conn,
                campaign_id,
            )

            if campaign is None:
                raise RunControlError(
                    "campaign_not_found",
                    "Campaign not found.",
                )

            counts = repo.status_counts(
                conn,
                campaign_id,
            )
        finally:
            conn.close()

        with self._lock:
            running = (
                self._thread is not None
                and self._thread.is_alive()
                and self._campaign_id == campaign_id
            )

            result = self._last_results.get(campaign_id)

        return {
            "campaign_id": campaign_id,
            "state": campaign.state,
            "running": running,
            "stop_requested": bool(
                running and self._stop is not None and self._stop.is_set()
            ),
            "counts": counts,
            "halt_reason": campaign.halt_reason,
            "last_result": (
                {
                    "state": result.state,
                    "reason": result.reason,
                }
                if result is not None
                else None
            ),
        }

    def _worker(
        self,
        campaign_id: int,
        sender: str,
        provider: GmailSmtpProvider,
        stop: threading.Event,
    ) -> None:
        try:
            runner = self._runner_factory(
                self._db_path,
                provider,
                sender,
            )
            result = runner.run(
                campaign_id,
                stop,
            )

            with self._lock:
                self._last_results[campaign_id] = result

        finally:
            with self._lock:
                self._thread = None
                self._stop = None
                self._campaign_id = None

    def _daily_cap_warning(
        self,
        conn: sqlite3.Connection,
        campaign_id: int,
    ) -> str | None:
        today = datetime.now(timezone.utc).date()
        start = f"{today.isoformat()}T00:00:00+00:00"

        sent_today = conn.execute(
            "SELECT COUNT(*) FROM recipients " "WHERE status = 'sent' AND sent_at >= ?",
            (start,),
        ).fetchone()[0]

        pending = conn.execute(
            "SELECT COUNT(*) FROM recipients "
            "WHERE campaign_id = ? AND status = 'pending'",
            (campaign_id,),
        ).fetchone()[0]

        projected = sent_today + pending

        if projected >= self._daily_cap:
            return (
                f"This run could reach or exceed the configured Gmail daily "
                f"recipient warning threshold of {self._daily_cap}."
            )

        return None
