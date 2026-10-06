from __future__ import annotations

import json
import sqlite3

from app.mail_core.renderer import extract_variables
from app.storage import repo


class CampaignError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CampaignService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self) -> list[dict]:
        return [self._to_dict(campaign) for campaign in repo.list_campaigns(self._conn)]

    def get(self, campaign_id: int) -> dict:
        campaign = self._require(campaign_id)
        return self._to_dict(campaign)

    def create(
        self,
        *,
        name: str,
        subject: str = "",
        body_html: str = "",
        variables: list[str] | None = None,
    ) -> dict:
        name = self._validate_name(name)

        campaign_id = repo.create_campaign(
            self._conn,
            name=name,
            subject=subject,
            body_html=body_html,
            variables=self._normalize_variables(variables or []),
        )

        return self.get(campaign_id)

    def update(
        self,
        campaign_id: int,
        *,
        name: str,
        subject: str,
        body_html: str,
        variables: list[str],
    ) -> dict:
        campaign = self._require(campaign_id)

        if campaign.state == "running":
            raise CampaignError(
                "campaign_running",
                "A running campaign cannot be edited.",
            )

        if campaign.locked:
            raise CampaignError(
                "campaign_locked",
                "This campaign has already sent an email and can no longer be edited.",
            )

        repo.update_campaign_content(
            self._conn,
            campaign_id,
            name=self._validate_name(name),
            subject=subject,
            body_html=body_html,
            variables=self._normalize_variables(variables),
        )

        # Any content edit requires a fresh preview.
        repo.set_state(
            self._conn,
            campaign_id,
            "draft",
            None,
        )

        return self.get(campaign_id)

    def duplicate(
        self,
        campaign_id: int,
        *,
        new_name: str,
        carry_recipients: bool = False,
    ) -> dict:
        self._require(campaign_id)

        new_id = repo.duplicate_campaign(
            self._conn,
            campaign_id,
            new_name=self._validate_name(new_name),
            carry_recipients=carry_recipients,
        )

        return self.get(new_id)

    def _require(self, campaign_id: int) -> repo.CampaignRow:
        campaign = repo.get_campaign(self._conn, campaign_id)

        if campaign is None:
            raise CampaignError(
                "campaign_not_found",
                "Campaign not found.",
            )

        return campaign

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()

        if not name:
            raise CampaignError(
                "invalid_name",
                "Campaign name is required.",
            )

        if len(name) > 200:
            raise CampaignError(
                "invalid_name",
                "Campaign name must be at most 200 characters.",
            )

        return name

    @staticmethod
    def _normalize_variables(variables: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for variable in variables:
            variable = variable.strip()

            if not variable or variable in seen:
                continue

            seen.add(variable)
            result.append(variable)

        return result

    def _to_dict(self, campaign: repo.CampaignRow) -> dict:
        row = self._conn.execute(
            "SELECT variables FROM campaigns WHERE id = ?",
            (campaign.id,),
        ).fetchone()

        declared_variables = json.loads(row["variables"]) if row else []
        detected_variables = extract_variables(
            f"{campaign.subject}\n{campaign.body_html}",
        )
        variables = detected_variables or declared_variables
        counts = {
            status: count
            for status, count in self._conn.execute(
                "SELECT status, COUNT(*) FROM recipients "
                "WHERE campaign_id = ? GROUP BY status",
                (campaign.id,),
            ).fetchall()
        }

        return {
            "id": campaign.id,
            "name": campaign.name,
            "subject": campaign.subject,
            "body_html": campaign.body_html,
            "variables": variables,
            "state": campaign.state,
            "locked": campaign.locked,
            "halt_reason": campaign.halt_reason,
            "counts": counts,
        }

    def delete(self, campaign_id: int) -> None:
        campaign = self._require(campaign_id)

        if campaign.state == "running":
            raise CampaignError(
                "campaign_running",
                "A running campaign cannot be deleted.",
            )

        repo.delete_campaign(
            self._conn,
            campaign_id,
        )
