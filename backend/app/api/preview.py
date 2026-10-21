from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.api.dependencies import get_db
from app.services.preview import PreviewError, PreviewService
from app.services.settings import SettingsService

router = APIRouter(tags=["preview"])


class AttachmentPreviewResponse(BaseModel):
    filename: str
    path: str
    size: int


class RecipientPreviewResponse(BaseModel):
    recipient_id: int
    email: str
    subject: str
    text: str
    html: str
    attachments: list[AttachmentPreviewResponse]


def _sender_email(request: Request) -> str:
    settings: SettingsService = request.app.state.settings_service
    sender = settings.get_sender_settings().email

    if not sender:
        raise PreviewError(
            "sender_not_configured",
            "Sender email is not configured.",
        )

    return sender


def _error(exc: PreviewError) -> JSONResponse:
    if exc.code in {
        "campaign_not_found",
        "recipient_not_found",
        "attachment_not_found",
    }:
        status_code = 404
    elif exc.code == "sender_not_configured":
        status_code = 400
    else:
        status_code = 422

    return JSONResponse(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
        status_code=status_code,
    )


def _service(request: Request, conn) -> PreviewService:
    return PreviewService(
        conn,
        sender=_sender_email(request),
    )


@router.post(
    "/api/campaigns/{campaign_id}/preview",
)
def preview_campaign(
    campaign_id: int,
    request: Request,
    conn=Depends(get_db),
) -> dict[str, Any]:
    try:
        return _service(request, conn).preview_campaign(
            campaign_id,
        )
    except PreviewError as exc:
        return _error(exc)


@router.get("/api/campaigns/{campaign_id}/recipients/{recipient_id}/attachments/{attachment_index}")
def recipient_attachment(
    campaign_id: int,
    recipient_id: int,
    attachment_index: int,
    conn=Depends(get_db),
):
    try:
        paths = PreviewService(conn, sender="").recipient_attachments(campaign_id, recipient_id)
        if attachment_index < 0 or attachment_index >= len(paths):
            raise PreviewError("attachment_not_found", "Attachment not found for this recipient.")
        path = paths[attachment_index]
        return FileResponse(
            path, filename=path.name, media_type="application/octet-stream",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except PreviewError as exc:
        return _error(exc)


@router.post(
    "/api/campaigns/{campaign_id}/recipients/{recipient_id}/preview",
    response_model=RecipientPreviewResponse,
)
def preview_recipient(
    campaign_id: int,
    recipient_id: int,
    request: Request,
    conn=Depends(get_db),
) -> dict[str, Any]:
    try:
        return _service(request, conn).preview_recipient(
            campaign_id,
            recipient_id,
        )
    except PreviewError as exc:
        return _error(exc)
