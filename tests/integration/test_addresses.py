import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f

ADDR = {
    "label": "Home",
    "recipient_name": "Ahmed Ali",
    "phone": "01012345678",
    "governorate": "Cairo",
    "city": "Nasr City",
    "street_address": "10 Example St",
}


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def user(session):
    return f.make_user(session)


def test_first_address_becomes_default(client, user):
    r = client.post("/addresses", json=ADDR, headers=_h(user))
    assert r.status_code == 201
    assert r.json()["is_default"] is True


def test_only_one_default_after_new_default(client, user):
    a = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    b = client.post("/addresses", json={**ADDR, "is_default": True}, headers=_h(user)).json()
    rows = client.get("/addresses", headers=_h(user)).json()
    defaults = [x["id"] for x in rows if x["is_default"]]
    assert defaults == [b["id"]]
    assert a["id"] != b["id"]


def test_second_address_not_default_by_default(client, user):
    client.post("/addresses", json=ADDR, headers=_h(user))
    b = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    assert b["is_default"] is False


def test_set_default_switches(client, user):
    a = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    b = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    r = client.post(f"/addresses/{b['id']}/default", headers=_h(user))
    assert r.status_code == 200
    rows = {x["id"]: x["is_default"] for x in client.get("/addresses", headers=_h(user)).json()}
    assert rows == {a["id"]: False, b["id"]: True}


def test_update_address(client, user):
    a = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    r = client.put(f"/addresses/{a['id']}", json={**ADDR, "city": "Giza"}, headers=_h(user))
    assert r.status_code == 200
    assert r.json()["city"] == "Giza"
    assert r.json()["is_default"] is True


def test_delete_default_promotes_another(client, user):
    a = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    b = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    assert client.delete(f"/addresses/{a['id']}", headers=_h(user)).status_code == 204
    rows = client.get("/addresses", headers=_h(user)).json()
    assert [(x["id"], x["is_default"]) for x in rows] == [(b["id"], True)]


def test_delete_last_address(client, user):
    a = client.post("/addresses", json=ADDR, headers=_h(user)).json()
    assert client.delete(f"/addresses/{a['id']}", headers=_h(user)).status_code == 204
    assert client.get("/addresses", headers=_h(user)).json() == []


@pytest.mark.parametrize("phone", ["0123", "02012345678", "abc", "010123456789"])
def test_bad_phone_rejected(client, user, phone):
    r = client.post("/addresses", json={**ADDR, "phone": phone}, headers=_h(user))
    assert r.status_code == 422


def test_blank_required_field_rejected(client, user):
    r = client.post("/addresses", json={**ADDR, "city": "   "}, headers=_h(user))
    assert r.status_code == 422


def test_requires_login(client):
    assert client.get("/addresses").status_code == 401
    assert client.post("/addresses", json=ADDR).status_code == 401


def test_cannot_touch_other_customers_address(client, session):
    owner = f.make_user(session)
    other = f.make_user(session)
    a = client.post("/addresses", json=ADDR, headers=_h(owner)).json()

    assert client.get("/addresses", headers=_h(other)).json() == []
    assert client.put(f"/addresses/{a['id']}", json=ADDR, headers=_h(other)).status_code == 404
    assert client.post(f"/addresses/{a['id']}/default", headers=_h(other)).status_code == 404
    assert client.delete(f"/addresses/{a['id']}", headers=_h(other)).status_code == 404
    # the owner still has it
    assert len(client.get("/addresses", headers=_h(owner)).json()) == 1


def test_user_id_in_body_is_ignored(client, session):
    owner = f.make_user(session)
    victim = f.make_user(session)
    r = client.post("/addresses", json={**ADDR, "user_id": victim.id}, headers=_h(owner))
    assert r.status_code == 201
    assert client.get("/addresses", headers=_h(victim)).json() == []
    assert len(client.get("/addresses", headers=_h(owner)).json()) == 1
