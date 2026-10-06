from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.providers.base import ProviderError
from app.services.settings import SettingsError, SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SenderSettingsResponse(BaseModel):
    email: str | None
    has_app_password: bool


class SenderCredentialsRequest(BaseModel):
    email: str
    app_password: str


_PROVIDER_ERROR_CODES = {
    "ProviderError": "provider_error",
    "AuthenticationFailed": "authentication_failed",
    "ConnectionLost": "connection_lost",
    "LimitReached": "limit_reached",
    "RecipientRejected": "recipient_rejected",
    "SenderRejected": "sender_rejected",
    "TemporaryFailure": "temporary_failure",
    "DeliveryUncertain": "delivery_uncertain",
}


def _provider_error(error: ProviderError) -> JSONResponse:
    code = _PROVIDER_ERROR_CODES.get(
        type(error).__name__,
        "provider_error",
    )

    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": str(error),
            }
        },
        status_code=502,
    )


def _service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def _settings_error(error: SettingsError) -> JSONResponse:
    if error.code == "test_cooldown":
        retry_after = ceil(error.retry_after or 1)

        return JSONResponse(
            {
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "retry_after": retry_after,
                }
            },
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    return JSONResponse(
        {
            "error": {
                "code": error.code,
                "message": error.message,
            }
        },
        status_code=400,
    )


@router.get("/sender", response_model=SenderSettingsResponse)
def get_sender_settings(request: Request) -> SenderSettingsResponse:
    settings = _service(request).get_sender_settings()

    return SenderSettingsResponse(
        email=settings.email,
        has_app_password=settings.has_app_password,
    )


@router.put("/sender", response_model=SenderSettingsResponse)
def save_sender_settings(
    payload: SenderCredentialsRequest,
    request: Request,
) -> SenderSettingsResponse:
    try:
        settings = _service(request).save_sender_credentials(
            payload.email,
            payload.app_password,
        )
    except SettingsError as exc:
        return _settings_error(exc)

    return SenderSettingsResponse(
        email=settings.email,
        has_app_password=settings.has_app_password,
    )


@router.post("/sender/test")
def test_sender_connection(request: Request) -> dict[str, str]:
    try:
        _service(request).test_saved_connection()
    except SettingsError as exc:
        return _settings_error(exc)
    except ProviderError as exc:
        return _provider_error(exc)

    return {"status": "ok"}
