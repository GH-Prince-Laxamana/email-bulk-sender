from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.providers.base import ProviderError
from app.services.send_test import TestSendError, TestSendService

router = APIRouter(
    prefix="/api/settings/sender",
    tags=["settings"],
)


def _service(request: Request) -> TestSendService:
    return request.app.state.test_send_service


def _provider_error(exc: ProviderError) -> JSONResponse:
    codes = {
        "AuthenticationFailed": "authentication_failed",
        "ConnectionLost": "connection_lost",
        "LimitReached": "limit_reached",
        "SenderRejected": "sender_rejected",
        "RecipientRejected": "recipient_rejected",
        "TemporaryFailure": "temporary_failure",
        "DeliveryUncertain": "delivery_uncertain",
        "ProviderError": "provider_error",
    }

    return JSONResponse(
        {
            "error": {
                "code": codes.get(
                    type(exc).__name__,
                    "provider_error",
                ),
                "message": str(exc),
            }
        },
        status_code=502,
    )


@router.post("/test-send", response_model=None)
def send_test_to_self(
    request: Request,
) -> dict[str, str] | JSONResponse:
    try:
        _service(request).send_to_self()
    except TestSendError as exc:
        return JSONResponse(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
            status_code=400,
        )
    except ProviderError as exc:
        return _provider_error(exc)

    return {
        "status": "sent",
    }
