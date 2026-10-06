from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_db
from app.services.recipients import RecipientError, RecipientService
from app.services.run_control import RunControlError, RunControlService

router = APIRouter(tags=["run-control"])


def _error(exc: RunControlError) -> JSONResponse:
    if exc.code == "campaign_not_found":
        status_code = 404
    elif exc.code in {
        "run_active",
        "run_not_active",
        "campaign_not_ready",
    }:
        status_code = 409
    elif exc.code == "credentials_missing":
        status_code = 400
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


def _recipient_error(exc: RecipientError) -> JSONResponse:
    if exc.code in {
        "campaign_not_found",
        "recipient_not_found",
    }:
        status_code = 404
    elif exc.code == "campaign_running":
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


def get_run_control(request) -> RunControlService:
    return request.app.state.run_control_service


@router.post("/api/campaigns/{campaign_id}/run", status_code=202)
def run_campaign(
    campaign_id: int,
    service: RunControlService = Depends(get_run_control),
) -> dict[str, Any]:
    try:
        return service.start(campaign_id)
    except RunControlError as exc:
        return _error(exc)


@router.post("/api/campaigns/{campaign_id}/stop")
def stop_campaign(
    campaign_id: int,
    service: RunControlService = Depends(get_run_control),
) -> dict[str, str]:
    try:
        service.stop(campaign_id)
    except RunControlError as exc:
        return _error(exc)

    return {
        "status": "stop_requested",
    }


@router.get("/api/campaigns/{campaign_id}/status")
def campaign_status(
    campaign_id: int,
    service: RunControlService = Depends(get_run_control),
) -> dict[str, Any]:
    try:
        return service.status(campaign_id)
    except RunControlError as exc:
        return _error(exc)


@router.post("/api/campaigns/{campaign_id}/retry-failed")
def retry_failed(
    campaign_id: int,
    conn=Depends(get_db),
) -> dict[str, int]:
    try:
        changed = RecipientService(conn).retry_failed(
            campaign_id,
        )
    except RecipientError as exc:
        return _recipient_error(exc)

    return {
        "reset": changed,
    }
