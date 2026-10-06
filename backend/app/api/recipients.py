from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_db
from app.services.recipients import RecipientError, RecipientService

router = APIRouter(tags=["recipients"])


class RecipientResponse(BaseModel):
    id: int
    email: str
    values: dict[str, Any]
    status: str
    error_code: str | None
    error_message: str | None
    attempts: int
    sent_at: str | None
    position: int


class ImportRecipientsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class RecipientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1)
    values: dict[str, str] = Field(default_factory=dict)


class ResolveInterruptedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retry: bool


def _error(exc: RecipientError) -> JSONResponse:
    if exc.code in {
        "campaign_not_found",
        "recipient_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "campaign_locked",
        "campaign_running",
        "recipient_not_interrupted",
        "duplicate_recipient",
    }:
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


@router.get(
    "/api/campaigns/{campaign_id}/recipients",
    response_model=list[RecipientResponse],
)
def list_recipients(
    campaign_id: int,
    conn=Depends(get_db),
) -> list[dict]:
    try:
        return RecipientService(conn).list(campaign_id)
    except RecipientError as exc:
        return _error(exc)


@router.post(
    "/api/campaigns/{campaign_id}/recipients",
    response_model=RecipientResponse,
    status_code=201,
)
def create_recipient(
    campaign_id: int,
    payload: RecipientRequest,
    conn=Depends(get_db),
) -> dict:
    try:
        return RecipientService(conn).create(
            campaign_id,
            email=payload.email,
            values=payload.values,
        )
    except RecipientError as exc:
        return _error(exc)


@router.patch(
    "/api/recipients/{recipient_id}",
    response_model=RecipientResponse,
)
def update_recipient(
    recipient_id: int,
    payload: RecipientRequest,
    conn=Depends(get_db),
) -> dict:
    try:
        return RecipientService(conn).update(
            recipient_id,
            email=payload.email,
            values=payload.values,
        )
    except RecipientError as exc:
        return _error(exc)


@router.delete(
    "/api/recipients/{recipient_id}",
    status_code=204,
)
def delete_recipient(
    recipient_id: int,
    conn=Depends(get_db),
) -> None:
    try:
        RecipientService(conn).delete(recipient_id)
    except RecipientError as exc:
        return _error(exc)


@router.post(
    "/api/campaigns/{campaign_id}/recipients/import",
)
def import_recipients(
    campaign_id: int,
    payload: ImportRecipientsRequest,
    conn=Depends(get_db),
) -> dict[str, Any]:
    try:
        return RecipientService(conn).import_csv(
            campaign_id,
            payload.text,
        )
    except RecipientError as exc:
        return _error(exc)


@router.post(
    "/api/campaigns/{campaign_id}/recipients/retry-failed",
)
def retry_failed_recipients(
    campaign_id: int,
    conn=Depends(get_db),
) -> dict[str, int]:
    try:
        changed = RecipientService(conn).retry_failed(campaign_id)
    except RecipientError as exc:
        return _error(exc)

    return {"reset": changed}


@router.post(
    "/api/recipients/{recipient_id}/resolve",
)
def resolve_interrupted_recipient(
    recipient_id: int,
    payload: ResolveInterruptedRequest,
    conn=Depends(get_db),
) -> dict[str, str]:
    try:
        RecipientService(conn).resolve_interrupted(
            recipient_id,
            retry=payload.retry,
        )
    except RecipientError as exc:
        return _error(exc)

    return {
        "status": "pending" if payload.retry else "sent",
    }
