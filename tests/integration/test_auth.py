from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.dependencies import require_role
from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.config import settings
from ai_commerce_marketplace.core.security import ALGORITHM, create_access_token, hash_password
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f

PASSWORD = "Passw0rd123"
VALID = {
    "full_name": "Test User",
    "email": "new@example.com",
    "phone": "01012345678",
    "password": PASSWORD,
}


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session

    @app.get("/seller-only")
    def seller_only(user: User = Depends(require_role("seller"))):
        return {"id": user.id}

    return TestClient(app, raise_server_exceptions=False)


def _login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- happy path ----
def test_register_login_me(client):
    r = client.post("/auth/register", json=VALID)
    assert r.status_code == 201
    assert r.json()["role"] == "customer"

    token = _login(client, VALID["email"]).json()["access_token"]
    me = client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["email"] == VALID["email"]


# ---- edge cases ----
def test_email_case_insensitive_login(client):
    client.post("/auth/register", json=VALID)
    r = _login(client, VALID["email"].upper())
    assert r.status_code == 200


def test_expired_token_rejected(client, session):
    user = f.make_user(session, password_hash=hash_password(PASSWORD))
    expired = jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    r = client.get("/auth/me", headers=_auth(expired))
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"


def test_token_contains_only_sub_role_exp(session):
    user = f.make_user(session)
    payload = jwt.decode(
        create_access_token(user.id, user.role), settings.jwt_secret, algorithms=[ALGORITHM]
    )
    assert set(payload) == {"sub", "role", "exp"}


# ---- failures ----
def test_duplicate_email_409(client):
    client.post("/auth/register", json=VALID)
    r = client.post("/auth/register", json={**VALID, "email": VALID["email"].upper()})
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


@pytest.mark.parametrize("bad", ["short1", "onlyletters", "12345678"])
def test_weak_password_422(client, bad):
    r = client.post("/auth/register", json={**VALID, "password": bad})
    assert r.status_code == 422


def test_bad_phone_422(client):
    r = client.post("/auth/register", json={**VALID, "phone": "0123"})
    assert r.status_code == 422


def test_wrong_password_401(client):
    client.post("/auth/register", json=VALID)
    r = _login(client, VALID["email"], "WrongPass999")
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_unknown_email_same_error_as_wrong_password(client):
    client.post("/auth/register", json=VALID)
    a = _login(client, VALID["email"], "WrongPass999").json()
    b = _login(client, "ghost@example.com").json()
    assert a == b


def test_cannot_self_register_as_seller(client):
    r = client.post("/auth/register", json={**VALID, "role": "seller"})
    assert r.status_code == 400
    assert r.json()["code"] == "role_not_allowed"


def test_me_without_token_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_401(client):
    assert client.get("/auth/me", headers=_auth("not.a.jwt")).status_code == 401


def test_inactive_user_cannot_login(client, session):
    f.make_user(
        session, email="off@example.com", password_hash=hash_password(PASSWORD), is_active=False
    )
    assert _login(client, "off@example.com").status_code == 401


def test_customer_gets_403_on_seller_endpoint(client):
    client.post("/auth/register", json=VALID)
    token = _login(client, VALID["email"]).json()["access_token"]
    r = client.get("/seller-only", headers=_auth(token))
    assert r.status_code == 403


def test_seller_allowed_on_seller_endpoint(client, session):
    seller = f.make_seller(session)
    user = session.get(User, seller.user_id)
    user.password_hash = hash_password(PASSWORD)
    session.flush()
    token = _login(client, user.email).json()["access_token"]
    assert client.get("/seller-only", headers=_auth(token)).status_code == 200


def test_password_never_in_responses(client):
    reg = client.post("/auth/register", json=VALID)
    token = _login(client, VALID["email"]).json()["access_token"]
    me = client.get("/auth/me", headers=_auth(token))
    for r in (reg, me):
        assert PASSWORD not in r.text
        assert "password" not in r.text.lower()
        assert "$argon2" not in r.text


def test_validation_error_does_not_echo_password(client):
    r = client.post("/auth/register", json={**VALID, "password": "onlyletters"})
    assert r.status_code == 422
    assert "onlyletters" not in r.text
