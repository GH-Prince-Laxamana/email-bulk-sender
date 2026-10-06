from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.security import LocalSecurityMiddleware, generate_app_token
from app.api.app import create_app
from app.storage.secret_store import FileSecretStore
from app.services.settings import SettingsService

TOKEN = generate_app_token()


def make_app(token: str = TOKEN) -> FastAPI:
    app = FastAPI()
    app.add_middleware(LocalSecurityMiddleware, token=token)

    @app.get("/api/test")
    def api_test():
        return {"ok": True}

    @app.get("/not-api")
    def not_api():
        return {"ok": True}

    return app


def test_valid_api_token_is_accepted():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "127.0.0.1",
            "X-App-Token": TOKEN,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_localhost_is_accepted():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "localhost:8000",
            "X-App-Token": TOKEN,
        },
    )

    assert response.status_code == 200


def test_missing_token_is_rejected():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={"Host": "127.0.0.1"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_wrong_token_is_rejected():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "127.0.0.1",
            "X-App-Token": "wrong-token",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_query_string_token_is_not_accepted():
    client = TestClient(make_app())

    response = client.get(
        f"/api/test?token={TOKEN}",
        headers={"Host": "127.0.0.1"},
    )

    assert response.status_code == 401


def test_disallowed_host_is_rejected():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "evil.example",
            "X-App-Token": TOKEN,
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid host"}


def test_host_subdomain_is_not_accepted():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "localhost.evil.example",
            "X-App-Token": TOKEN,
        },
    )

    assert response.status_code == 403


def test_non_api_request_does_not_require_token():
    client = TestClient(make_app())

    response = client.get(
        "/not-api",
        headers={"Host": "127.0.0.1"},
    )

    assert response.status_code == 200


def test_api_token_is_not_exposed_in_error_response():
    client = TestClient(make_app())

    response = client.get(
        "/api/test",
        headers={
            "Host": "127.0.0.1",
            "X-App-Token": "wrong-token",
        },
    )

    assert TOKEN not in response.text


def test_empty_configured_token_is_rejected():
    app = FastAPI()

    try:
        LocalSecurityMiddleware(app, "")
    except ValueError as exc:
        assert str(exc) == "API token must not be empty"
    else:
        raise AssertionError("Expected ValueError")


def test_create_app_wires_security_middleware(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    service = SettingsService(store)

    client = TestClient(create_app(TOKEN, service))

    response = client.get(
        "/api/health",
        headers={
            "Host": "127.0.0.1",
            "X-App-Token": TOKEN,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}