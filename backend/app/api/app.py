from __future__ import annotations

from fastapi import FastAPI

from app.api.attachments import router as attachments_router
from app.api.campaigns import router as campaigns_router
from app.api.preview import router as preview_router
from app.api.recipients import router as recipients_router
from app.api.run_control import router as run_control_router
from app.api.security import LocalSecurityMiddleware
from app.api.settings import router as settings_router
from app.api.test_send import router as test_send_router
from app.config import database_path
from app.services.run_control import RunControlService
from app.services.send_test import TestSendService
from app.services.settings import SettingsService
from app.storage.secret_store import default_secret_store
from app.api.frontend import router as frontend_router
from fastapi.staticfiles import StaticFiles
from app.api.frontend import DIST_DIR


def create_app(
    token: str,
    settings_service: SettingsService,
) -> FastAPI:
    app = FastAPI()

    app.mount(
        "/assets",
        StaticFiles(directory=DIST_DIR / "assets"),
        name="frontend-assets",
    )

    app.state.settings_service = settings_service

    secret_store = default_secret_store(
        database_path().parent,
    )

    app.state.run_control_service = RunControlService(
        database_path(),
        settings_service,
        secret_store,
    )

    app.state.test_send_service = TestSendService(
        settings_service,
        secret_store,
    )

    app.add_middleware(
        LocalSecurityMiddleware,
        token=token,
    )

    app.include_router(settings_router)
    app.include_router(campaigns_router)
    app.include_router(recipients_router)
    app.include_router(attachments_router)
    app.include_router(preview_router)
    app.include_router(run_control_router)
    app.include_router(test_send_router)
    app.include_router(frontend_router)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app
