from __future__ import annotations

import os

from pathlib import Path
import sqlite3
from typing import Any

from app.storage import repo
from app.storage.db import transaction

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.api.dependencies import get_db

router = APIRouter(tags=["attachments"])


class AttachmentError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AttachmentService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, campaign_id: int) -> list[dict[str, Any]]:
        self._require_campaign(campaign_id)

        return repo.get_attachment_rules(
            self._conn,
            campaign_id,
        )

    def replace(
        self,
        campaign_id: int,
        rules: list[dict[str, str | None]],
    ) -> list[dict[str, Any]]:
        campaign = self._require_campaign(campaign_id)
        self._ensure_editable(campaign)

        normalized = [self._validate_rule(rule) for rule in rules]

        repo.replace_attachment_rules(
            self._conn,
            campaign_id,
            normalized,
        )

        # Attachment changes invalidate an existing preview.
        if campaign.state != "draft":
            repo.set_state(
                self._conn,
                campaign_id,
                "draft",
                None,
            )

        return repo.get_attachment_rules(
            self._conn,
            campaign_id,
        )

    @staticmethod
    def check_path(path: str) -> dict[str, Any]:
        raw = path.strip()

        if not raw:
            raise AttachmentError(
                "invalid_path",
                "Path is required.",
            )

        target = Path(raw)

        try:
            resolved = target.resolve(strict=False)
        except OSError as exc:
            raise AttachmentError(
                "invalid_path",
                "The path could not be resolved.",
            ) from exc

        exists = resolved.exists()

        return {
            "path": str(resolved),
            "exists": exists,
            "is_file": exists and resolved.is_file(),
            "is_directory": exists and resolved.is_dir(),
        }

    def _require_campaign(self, campaign_id: int) -> repo.CampaignRow:
        campaign = repo.get_campaign(
            self._conn,
            campaign_id,
        )

        if campaign is None:
            raise AttachmentError(
                "campaign_not_found",
                "Campaign not found.",
            )

        return campaign

    @staticmethod
    def _ensure_editable(campaign: repo.CampaignRow) -> None:
        if campaign.locked:
            raise AttachmentError(
                "campaign_locked",
                "This campaign has already sent an email and can no longer be edited.",
            )

        if campaign.state == "running":
            raise AttachmentError(
                "campaign_running",
                "A running campaign cannot be edited.",
            )

    @staticmethod
    def _validate_rule(
        rule: dict[str, str | None],
    ) -> dict[str, str | None]:
        path = (rule.get("path") or "").strip()
        folder = (rule.get("folder") or "").strip()
        filename_template = (rule.get("filename_template") or "").strip()

        fixed = bool(path)
        templated = bool(folder or filename_template)

        if fixed and templated:
            raise AttachmentError(
                "invalid_attachment_rule",
                "An attachment rule must use either a fixed path or a folder and filename template.",
            )

        if not fixed and not templated:
            raise AttachmentError(
                "invalid_attachment_rule",
                "An attachment rule is empty.",
            )

        if fixed:
            return {
                "path": path,
                "folder": None,
                "filename_template": None,
            }

        if not folder or not filename_template:
            raise AttachmentError(
                "invalid_attachment_rule",
                "A folder and filename template are both required.",
            )

        return {
            "path": None,
            "folder": folder,
            "filename_template": filename_template,
        }


def _error(exc: AttachmentError) -> JSONResponse:
    if exc.code == "campaign_not_found":
        status_code = 404
    elif exc.code in {"campaign_locked", "campaign_running"}:
        status_code = 409
    else:
        status_code = 400

    return JSONResponse(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
        status_code=status_code,
    )


@router.get("/api/campaigns/{campaign_id}/attachments")
def list_attachments(
    campaign_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return AttachmentService(conn).list(campaign_id)
    except AttachmentError as exc:
        return _error(exc)


@router.put("/api/campaigns/{campaign_id}/attachments")
def replace_attachments(
    campaign_id: int,
    rules: list[dict[str, str | None]],
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return AttachmentService(conn).replace(
            campaign_id,
            rules,
        )
    except AttachmentError as exc:
        return _error(exc)


@router.post("/api/paths/check")
def check_path(
    payload: dict[str, str],
) -> dict[str, Any]:
    try:
        return AttachmentService.check_path(
            payload.get("path", ""),
        )
    except AttachmentError as exc:
        return _error(exc)
