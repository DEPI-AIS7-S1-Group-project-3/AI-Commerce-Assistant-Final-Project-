import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.services.policies import split_sections
from tests import factories as f

BODY = """# سياسة الإرجاع

> سياسة تجريبية.

## 1. مهلة الإرجاع
خلال 14 يوم من التسليم.

## 2. شروط الإرجاع
- المنتج قابل للإرجاع.
- بحالته الأصلية.

## 10. الاسترداد
لنفس وسيلة الدفع.
"""


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


# ---- pure section splitter ----
def test_split_sections_numbers_titles_bodies():
    sections = split_sections(BODY)
    assert [(s.no, s.title) for s in sections] == [
        (1, "مهلة الإرجاع"),
        (2, "شروط الإرجاع"),
        (10, "الاسترداد"),
    ]
    assert sections[0].body == "خلال 14 يوم من التسليم."
    assert sections[1].body == "- المنتج قابل للإرجاع.\n- بحالته الأصلية."


def test_split_sections_ignores_intro_and_unnumbered_headings():
    assert split_sections("# عنوان\n\nمقدمة\n\n## ملاحظات\nنص") == []


def test_split_sections_on_seed_policies(session):
    # every real policy is numbered 1..n with no gaps
    from scripts.seed_database import _load

    for p in _load("policies.json"):
        nos = [s.no for s in split_sections(p["body_md"])]
        assert nos == list(range(1, len(nos) + 1)), p["slug"]
        assert nos, p["slug"]


# ---- API ----
def test_list_current_policies_in_page_order(client, session):
    f.make_policy(session, slug="warranty", category="warranty", title_ar="الضمان")
    f.make_policy(session, slug="returns", category="returns")
    f.make_policy(session, slug="shipping", category="shipping", title_ar="الشحن")
    f.make_policy(session, slug="returns", version="2025-01-01", is_current=False)
    r = client.get("/policies")
    assert r.status_code == 200
    assert [p["slug"] for p in r.json()] == ["shipping", "returns", "warranty"]
    assert set(r.json()[0]) == {"slug", "category", "title_ar", "version"}


def test_get_policy_returns_current_version_with_sections(client, session):
    f.make_policy(session, slug="returns", version="2025-01-01", is_current=False, body_md="قديم")
    f.make_policy(session, slug="returns", version="2026-10-01", body_md=BODY)
    r = client.get("/policies/returns")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "2026-10-01"
    assert body["body_md"] == BODY
    assert [s["no"] for s in body["sections"]] == [1, 2, 10]


def test_unknown_policy_404(client):
    r = client.get("/policies/privacy")
    assert r.status_code == 404
    assert r.json()["code"] == "policy_not_found"


def test_policies_are_public(client, session):
    f.make_policy(session)
    assert client.get("/policies").status_code == 200
    assert client.get("/policies/returns").status_code == 200
