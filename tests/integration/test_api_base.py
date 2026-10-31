from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.exceptions import NotFoundError


def make_client() -> TestClient:
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    @app.get("/missing")
    def missing():
        raise NotFoundError()

    # raise_server_exceptions=False lets us assert on the 500 response itself.
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok():
    r = make_client().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "x-request-id" in r.headers


def test_unknown_route_uses_unified_shape():
    r = make_client().get("/nope")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details"}


def test_app_error_uses_unified_shape():
    r = make_client().get("/missing")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


def test_unexpected_error_returns_500_without_stack_trace():
    r = make_client().get("/boom")
    assert r.status_code == 500
    assert r.json()["code"] == "internal_error"
    assert "secret internal detail" not in r.text
    assert "Traceback" not in r.text
