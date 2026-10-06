from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

APP_TOKEN_HEADER = "x-app-token"
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}


def generate_app_token() -> str:
    """Generate a cryptographically random per-launch API token."""
    return secrets.token_urlsafe(32)


def _host_is_allowed(host: str | None) -> bool:
    if not host:
        return False

    # Expected forms:
    # localhost
    # localhost:8000
    # 127.0.0.1
    # 127.0.0.1:8000
    hostname = host.rsplit(":", 1)[0].lower()

    # Do not accept malformed/alternate hosts.
    return hostname in ALLOWED_HOSTS


class LocalSecurityMiddleware:
    """
    Local-app security boundary.

    - Validates Host for every HTTP request.
    - Requires X-App-Token for every /api request.
    - Uses constant-time token comparison.
    - Never includes the expected token in responses.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        if not token:
            raise ValueError("API token must not be empty")

        self.app = app
        self.token = token

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host = headers.get("host")

        if not _host_is_allowed(host):
            response = JSONResponse(
                {"detail": "Invalid host"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        path = scope.get("path", "")
        is_api_request = path == "/api" or path.startswith("/api/")

        if is_api_request:
            provided_token = headers.get(APP_TOKEN_HEADER)

            if not provided_token or not secrets.compare_digest(
                provided_token, self.token
            ):
                response = JSONResponse(
                    {"detail": "Unauthorized"},
                    status_code=401,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
