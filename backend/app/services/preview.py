from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from app.mail_core.builder import (
    AttachmentRule,
    BuildError,
    Content,
    Recipient,
    build_message,
)
from app.storage import repo


class PreviewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PreviewResult:
    recipient_id: int
    email: str
    subject: str
    text: str
    html: str


class PreviewService:
    def __init__(
        self,
        conn,
        *,
        sender: str,
    ) -> None:
        self._conn = conn
        self._sender = sender

    def preview_campaign(
        self,
        campaign_id: int,
    ) -> dict[str, Any]:
        campaign = self._require_campaign(campaign_id)

        recipients = repo.pending_recipients(
            self._conn,
            campaign_id,
        )

        rules = self._attachment_rules(campaign_id)
        content = Content(
            subject=campaign.subject,
            body_html=campaign.body_html,
        )

        previews: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for recipient in recipients:
            try:
                message = build_message(
                    self._sender,
                    content,
                    rules,
                    Recipient(
                        email=recipient.email,
                        values=recipient.values,
                    ),
                    attach_files=False,
                )

                previews.append(
                    self._message_result(
                        recipient.id,
                        recipient.email,
                        message,
                    )
                )
            except BuildError as exc:
                errors.append(
                    {
                        "recipient_id": recipient.id,
                        "email": recipient.email,
                        "code": exc.code,
                        "message": str(exc),
                    }
                )

        if errors:
            if campaign.state != "draft":
                repo.set_state(
                    self._conn,
                    campaign_id,
                    "draft",
                    None,
                )

            return {
                "state": "draft",
                "clean": False,
                "total": len(recipients),
                "valid": len(previews),
                "invalid": len(errors),
                "errors": errors,
                "previews": previews,
            }

        next_state = (
            campaign.state
            if campaign.state == "finished" and not recipients
            else "previewed"
        )

        if next_state != campaign.state:
            repo.set_state(
                self._conn,
                campaign_id,
                next_state,
                None,
            )

        return {
            "state": next_state,
            "clean": True,
            "total": len(recipients),
            "valid": len(previews),
            "invalid": 0,
            "errors": [],
            "previews": previews,
        }

    def preview_recipient(
        self,
        campaign_id: int,
        recipient_id: int,
    ) -> dict[str, Any]:
        self._require_campaign(campaign_id)

        recipient = repo.get_recipient(
            self._conn,
            recipient_id,
        )

        if recipient is None:
            raise PreviewError(
                "recipient_not_found",
                "Recipient not found.",
            )

        owner = self._recipient_campaign_id(recipient_id)

        if owner != campaign_id:
            raise PreviewError(
                "recipient_not_found",
                "Recipient not found for this campaign.",
            )

        campaign = self._require_campaign(campaign_id)

        rules = self._attachment_rules(campaign_id)
        content = Content(
            subject=campaign.subject,
            body_html=campaign.body_html,
        )

        try:
            message = build_message(
                self._sender,
                content,
                rules,
                Recipient(
                    email=recipient.email,
                    values=recipient.values,
                ),
                attach_files=False,
            )
        except BuildError as exc:
            raise PreviewError(
                exc.code,
                str(exc),
            ) from exc

        return self._message_result(
            recipient.id,
            recipient.email,
            message,
        )

    def _require_campaign(self, campaign_id: int) -> repo.CampaignRow:
        campaign = repo.get_campaign(
            self._conn,
            campaign_id,
        )

        if campaign is None:
            raise PreviewError(
                "campaign_not_found",
                "Campaign not found.",
            )

        return campaign

    def _attachment_rules(
        self,
        campaign_id: int,
    ) -> list[AttachmentRule]:
        return [
            AttachmentRule(
                path=row["path"],
                folder=row["folder"],
                filename_template=row["filename_template"],
            )
            for row in repo.get_attachment_rules(
                self._conn,
                campaign_id,
            )
        ]

    def _recipient_campaign_id(
        self,
        recipient_id: int,
    ) -> int:
        row = self._conn.execute(
            "SELECT campaign_id FROM recipients WHERE id = ?",
            (recipient_id,),
        ).fetchone()

        if row is None:
            raise PreviewError(
                "recipient_not_found",
                "Recipient not found.",
            )

        return int(row["campaign_id"])

    @staticmethod
    def _message_result(
        recipient_id: int,
        email: str,
        message: EmailMessage,
    ) -> dict[str, Any]:
        html_part = message.get_body(
            preferencelist=("html",),
        )
        text_part = message.get_body(
            preferencelist=("plain",),
        )

        return {
            "recipient_id": recipient_id,
            "email": email,
            "subject": str(message["Subject"] or ""),
            "text": text_part.get_content() if text_part else "",
            "html": html_part.get_content() if html_part else "",
        }
