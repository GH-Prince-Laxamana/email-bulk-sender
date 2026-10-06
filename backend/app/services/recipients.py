from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from app.storage import repo
from app.storage.db import transaction


class RecipientError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RecipientService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, campaign_id: int) -> list[dict[str, Any]]:
        self._require_campaign(campaign_id)

        return [
            self._to_dict(recipient)
            for recipient in repo.list_recipients(
                self._conn,
                campaign_id,
            )
        ]

    def import_csv(
        self,
        campaign_id: int,
        text: str,
    ) -> dict[str, Any]:
        campaign = self._require_campaign(campaign_id)
        self._ensure_editable(campaign)

        rows = self._parse_csv(text)

        if not rows:
            raise RecipientError(
                "empty_import",
                "The import contains no recipient rows.",
            )

        recipients = self._rows_to_recipients(rows)

        with transaction(self._conn):
            inserted = repo.insert_recipients(
                self._conn,
                campaign_id,
                recipients,
            )

            # Adding recipients is a campaign edit, so a previous preview
            # is no longer valid.
            if campaign.state != "draft":
                repo.set_state(
                    self._conn,
                    campaign_id,
                    "draft",
                    None,
                )

        return {
            "inserted": inserted,
            "ignored_duplicates": len(recipients) - inserted,
            "total_rows": len(recipients),
        }

    def retry_failed(self, campaign_id: int) -> int:
        campaign = self._require_campaign(campaign_id)

        if campaign.state == "running":
            raise RecipientError(
                "campaign_running",
                "Recipients cannot be changed while the campaign is running.",
            )

        changed = repo.retry_failed(
            self._conn,
            campaign_id,
        )

        if changed and campaign.state == "finished":
            repo.set_state(
                self._conn,
                campaign_id,
                "paused",
                "Failed recipients were reset and are ready to retry.",
            )

        return changed

    def resolve_interrupted(
        self,
        recipient_id: int,
        *,
        retry: bool,
    ) -> None:
        recipient = repo.get_recipient(
            self._conn,
            recipient_id,
        )

        if recipient is None:
            raise RecipientError(
                "recipient_not_found",
                "Recipient not found.",
            )

        campaign_id = self._recipient_campaign_id(recipient_id)
        campaign = self._require_campaign(campaign_id)

        if campaign.state == "running":
            raise RecipientError(
                "campaign_running",
                "An interrupted recipient cannot be changed while the campaign is running.",
            )

        if recipient.status != "interrupted":
            raise RecipientError(
                "recipient_not_interrupted",
                "Only interrupted recipients can be resolved.",
            )

        repo.resolve_interrupted(
            self._conn,
            recipient_id,
            retry=retry,
        )

        if retry:
            repo.set_state(
                self._conn,
                campaign_id,
                "paused",
                "An interrupted recipient was reset and is ready to retry.",
            )


    def _require_campaign(self, campaign_id: int) -> repo.CampaignRow:
        campaign = repo.get_campaign(
            self._conn,
            campaign_id,
        )

        if campaign is None:
            raise RecipientError(
                "campaign_not_found",
                "Campaign not found.",
            )

        return campaign

    @staticmethod
    def _ensure_editable(campaign: repo.CampaignRow) -> None:
        if campaign.locked:
            raise RecipientError(
                "campaign_locked",
                "This campaign has already sent an email and can no longer be edited.",
            )

        if campaign.state == "running":
            raise RecipientError(
                "campaign_running",
                "A running campaign cannot be edited.",
            )

    def _recipient_campaign_id(self, recipient_id: int) -> int:
        row = self._conn.execute(
            "SELECT campaign_id FROM recipients WHERE id = ?",
            (recipient_id,),
        ).fetchone()

        if row is None:
            raise RecipientError(
                "recipient_not_found",
                "Recipient not found.",
            )

        return int(row["campaign_id"])

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, str]]:
        if not text.strip():
            raise RecipientError(
                "empty_import",
                "The import is empty.",
            )

        sample = text[:4096]
        delimiter = "\t" if "\t" in sample.splitlines()[0] else ","

        reader = csv.reader(
            io.StringIO(text),
            delimiter=delimiter,
        )

        try:
            raw_headers = next(reader)
        except StopIteration:
            raise RecipientError(
                "empty_import",
                "The import is empty.",
            ) from None

        headers = [header.strip() for header in raw_headers]

        if not headers:
            raise RecipientError(
                "missing_header",
                "The import must contain a header row.",
            )

        normalized = [header.casefold() for header in headers]

        if "email" not in normalized:
            raise RecipientError(
                "missing_email_column",
                "The import must contain an email column.",
            )

        if normalized.count("email") > 1:
            raise RecipientError(
                "duplicate_email_column",
                "The import contains more than one email column.",
            )

        if any(not header for header in headers):
            raise RecipientError(
                "invalid_header",
                "Column headers cannot be blank.",
            )

        seen_headers: set[str] = set()

        for header in headers:
            key = header.casefold()
            if key in seen_headers:
                raise RecipientError(
                    "duplicate_column",
                    f"Duplicate column: {header}",
                )
            seen_headers.add(key)

        result: list[dict[str, str]] = []

        for row_number, values in enumerate(reader, start=2):
            # Ignore completely blank rows.
            if not any(value.strip() for value in values):
                continue

            if len(values) != len(headers):
                raise RecipientError(
                    "invalid_row",
                    f"Row {row_number} does not match the header column count.",
                )

            result.append(
                {header: value.strip() for header, value in zip(headers, values)}
            )

        return result

    @staticmethod
    def _rows_to_recipients(
        rows: list[dict[str, str]],
    ) -> list[tuple[str, dict[str, str]]]:
        email_header = next(
            header for header in rows[0] if header.casefold() == "email"
        )

        recipients: list[tuple[str, dict[str, str]]] = []
        seen_emails: set[str] = set()

        for row_number, row in enumerate(rows, start=2):
            email = row[email_header].strip()

            if not email:
                raise RecipientError(
                    "missing_email",
                    f"Row {row_number} has no email address.",
                )

            email_key = email.casefold()

            if email_key in seen_emails:
                continue

            seen_emails.add(email_key)

            values = {
                key: value for key, value in row.items() if key.casefold() != "email"
            }

            recipients.append((email, values))

        return recipients

    @staticmethod
    def _to_dict(recipient: repo.RecipientDetailRow) -> dict[str, Any]:
        return {
            "id": recipient.id,
            "email": recipient.email,
            "values": recipient.values,
            "status": recipient.status,
            "error_code": recipient.error_code,
            "error_message": recipient.error_message,
            "attempts": recipient.attempts,
            "sent_at": recipient.sent_at,
            "position": recipient.position,
        }
