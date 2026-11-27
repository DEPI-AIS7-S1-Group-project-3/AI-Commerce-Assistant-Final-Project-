from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_commerce_marketplace.agents.router.graph import handle_chat
from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.api.routes.assistant import get_llm
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.conversation import ChatMessage, Conversation
from ai_commerce_marketplace.database.models.order import Order
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.llm import AllProvidersFailed
from tests import factories as f
from tests.fakes import FakeLLM, call, say


def make_client(session, llm):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: llm
    return TestClient(app, raise_server_exceptions=False)


def headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def chat(client, message, user=None, conversation_id=None):
    body = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/assistant/chat", json=body, headers=headers(user) if user else {})


def test_visitor_gets_shopping_and_a_stored_conversation(session):
    llm = FakeLLM(say("عندنا موبايلات كتير، تحب تحدد الميزانية؟"))
    client = make_client(session, llm)
    r = chat(client, "عايز موبايل")
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "shopping"
    assert body["needs_confirmation"] is None
    conv = session.get(Conversation, body["conversation_id"])
    assert conv.user_id is None and conv.role == "visitor" and conv.last_agent == "shopping"
    rows = session.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv.id)).all()
    assert [m.role for m in rows] == ["user", "assistant"]


def test_second_message_sees_the_first_as_history(session):
    llm = FakeLLM(say("أهلا، تحب أي نوع؟"), say("تمام"))
    client = make_client(session, llm)
    first = chat(client, "عايز موبايل").json()
    chat(client, "وبكام؟", conversation_id=first["conversation_id"])
    sent = llm.sent[1][0]
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1].content == "عايز موبايل"


def test_unsure_message_asks_the_llm_for_a_label(session):
    llm = FakeLLM(say('{"agent": "support"}'), say("اسأل عن الضمان أو الشحن"))
    r = chat(make_client(session, llm), "اهلا")
    assert r.json()["agent"] == "support"
    assert len(llm.sent) == 2


def test_bad_label_falls_back_to_shopping(session):
    llm = FakeLLM(say('{"agent": "order_actions"}'), say("أهلا"))  # a visitor cannot use it
    r = chat(make_client(session, llm), "اهلا")
    assert r.json()["agent"] == "shopping"


def test_visitor_asking_to_cancel_is_sent_to_support(session):
    llm = FakeLLM(
        call("order_get", {"order_id": 10002}),
        say("لازم تسجل دخول الأول."),
    )
    r = chat(make_client(session, llm), "ألغي طلب 10002")
    assert r.json()["agent"] == "support"


@pytest.fixture
def customer_order(session):
    user = f.make_user(session)
    order = f.make_order(session, customer_id=user.id, status="pending")
    f.make_order_item(session, order)
    return user, order


def test_cancel_needs_a_yes_and_runs_once(session, customer_order):
    user, order = customer_order
    llm = FakeLLM(
        call("cancel_order", {"order_id": order.id}),
        say("متأكد؟"),  # the model's own wording is replaced by the fixed question
        say("اتفضل"),  # the answer to the third message
    )
    client = make_client(session, llm)
    first = chat(client, f"ألغي طلب {order.id}", user).json()
    assert first["agent"] == "order_actions"
    assert first["needs_confirmation"]["question"].startswith("هتلغي الطلب")
    session.refresh(order)
    assert order.status == "pending"  # nothing changed yet

    second = chat(client, "أيوه", user, first["conversation_id"]).json()
    session.refresh(order)
    assert order.status == "cancelled"
    assert "تم إلغاء" in second["reply"]
    assert len(llm.sent) == 2  # the yes did not call the model

    third = chat(client, "أيوه", user, first["conversation_id"]).json()
    assert "تم إلغاء" not in third["reply"]  # no second cancel


def test_anything_but_yes_drops_the_pending_action(session, customer_order):
    user, order = customer_order
    llm = FakeLLM(call("cancel_order", {"order_id": order.id}), say("؟"), say("الضمان سنة"))
    client = make_client(session, llm)
    first = chat(client, f"ألغي طلب {order.id}", user).json()
    chat(client, "الضمان كام؟", user, first["conversation_id"])
    chat(client, "أيوه", user, first["conversation_id"])  # too late: the action was dropped
    session.refresh(order)
    assert order.status == "pending"


def test_pending_action_expires(session, customer_order):
    user, order = customer_order
    t0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    llm = FakeLLM(call("cancel_order", {"order_id": order.id}), say("؟"), say("تمام"))
    first = handle_chat(session, llm, user, f"ألغي طلب {order.id}", now=t0)
    assert first.needs_confirmation
    handle_chat(session, llm, user, "أيوه", first.conversation_id, now=t0 + timedelta(minutes=11))
    session.refresh(order)
    assert order.status == "pending"


def test_a_conversation_is_only_reachable_by_its_owner(session, customer_order):
    user, order = customer_order
    other = f.make_user(session)
    llm = FakeLLM(say("أهلا"), say("أهلا"), say("أهلا"))
    client = make_client(session, llm)
    cid = chat(client, "عايز موبايل", user).json()["conversation_id"]
    assert chat(client, "عايز موبايل", other, cid).status_code == 404
    assert chat(client, "عايز موبايل", None, cid).status_code == 404
    assert chat(client, "عايز موبايل", user, "not-a-uuid").status_code == 404


def test_another_user_cannot_confirm_someones_action(session, customer_order):
    user, order = customer_order
    other = f.make_user(session)
    llm = FakeLLM(call("cancel_order", {"order_id": order.id}), say("؟"))
    client = make_client(session, llm)
    cid = chat(client, f"ألغي طلب {order.id}", user).json()["conversation_id"]
    assert chat(client, "أيوه", other, cid).status_code == 404
    session.refresh(order)
    assert order.status == "pending"


def test_a_false_cancel_claim_is_replaced(session, customer_order):
    user, order = customer_order
    llm = FakeLLM(say("تم إلغاء الطلب رقم 10002 بنجاح."))
    r = chat(make_client(session, llm), "ألغي طلب 10002", user).json()
    assert "تم إلغاء" not in r["reply"]
    assert r["needs_confirmation"] is None


def test_seller_goes_to_the_seller_agent(session):
    user = f.make_user(session, role="seller")
    f.make_seller(session, user_id=user.id)
    llm = FakeLLM(say("مفيش مبيعات"))
    r = chat(make_client(session, llm), "ألغي طلب 10002", user).json()
    assert r["agent"] == "seller"


def test_llm_down_gives_503(session):
    llm = FakeLLM(AllProvidersFailed("all down"))
    r = chat(make_client(session, llm), "عايز موبايل")
    assert r.status_code == 503
    assert r.json()["code"] == "assistant_unavailable"


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_bad_input_is_rejected_before_the_llm(session, message):
    llm = FakeLLM()
    r = chat(make_client(session, llm), message)
    assert r.status_code == 422
    assert llm.sent == []


def test_bad_token_is_an_error_not_a_visitor(session):
    client = make_client(session, FakeLLM())
    r = client.post(
        "/assistant/chat", json={"message": "hi"}, headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401


def test_trace_is_hidden_unless_enabled(session, monkeypatch):
    llm = FakeLLM(say("أهلا"), say("أهلا"))
    client = make_client(session, llm)
    assert chat(client, "عايز موبايل").json()["trace"] is None
    from ai_commerce_marketplace.core.config import settings

    monkeypatch.setattr(settings, "assistant_debug_trace", True)
    trace = chat(client, "عايز موبايل").json()["trace"]
    assert trace["route"]["by"] == "rule" and trace["tools"] == []


def test_orders_table_untouched_by_a_visitor(session):
    before = session.scalar(select(Order.id).limit(1))
    llm = FakeLLM(say("أهلا"))
    chat(make_client(session, llm), "عايز موبايل")
    assert session.scalar(select(Order.id).limit(1)) == before


def test_a_stale_yes_gets_a_fixed_reply_and_never_calls_the_model(session, customer_order):
    user, order = customer_order
    t0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    llm = FakeLLM(call("cancel_order", {"order_id": order.id}), say("؟"))
    first = handle_chat(session, llm, user, f"ألغي طلب {order.id}", now=t0)
    late = handle_chat(
        session, llm, user, "أيوه", first.conversation_id, now=t0 + timedelta(minutes=11)
    )
    assert "مفيش حاجة مستنية تأكيدك" in late.reply
    assert late.agent == "order_actions"
    assert len(llm.sent) == 2  # the late yes did not reach the model
    session.refresh(order)
    assert order.status == "pending"


@pytest.fixture
def small_limit(monkeypatch):
    from ai_commerce_marketplace.api.rate_limit import assistant_limiter
    from ai_commerce_marketplace.core.config import settings

    monkeypatch.setattr(settings, "assistant_rate_limit_per_minute", 2)
    assistant_limiter.reset()
    yield
    assistant_limiter.reset()


def test_the_third_message_in_a_minute_gets_429_with_a_clear_code(session, small_limit):
    client = make_client(session, FakeLLM(say("1"), say("2"), say("3")))
    assert chat(client, "عايز موبايل").status_code == 200
    assert chat(client, "عايز لابتوب").status_code == 200
    r = chat(client, "عايز سماعة")
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"


def test_the_limit_is_per_user_not_global(session, small_limit, customer_order):
    user, _ = customer_order
    client = make_client(session, FakeLLM(*[say("ok")] * 6))
    for _ in range(2):
        assert chat(client, "عايز موبايل").status_code == 200
    assert chat(client, "عايز موبايل").status_code == 429
    assert chat(client, "عايز موبايل", user).status_code == 200  # another caller, own window


def test_limiter_window_slides():
    from ai_commerce_marketplace.api.rate_limit import RateLimitedError, SlidingWindowLimiter

    lim = SlidingWindowLimiter(window_s=60)
    lim.check("k", 1, now=0)
    with pytest.raises(RateLimitedError):
        lim.check("k", 1, now=30)
    lim.check("k", 1, now=61)  # the old hit left the window
    lim.check("k", 0, now=62)  # 0 disables


def test_the_next_turn_knows_which_products_were_shown(session):
    f.make_product(session, title_ar="لابتوب تجريبي أول")
    f.make_product(session, title_ar="لابتوب تجريبي ثاني")
    llm = FakeLLM(
        call("search_products", {"limit": 3}),
        say("دول الترشيحات"),
        say("تمام"),
    )
    client = make_client(session, llm)
    first = chat(client, "عايز لابتوب").json()
    assert first["products"], "the first answer must carry cards"
    chat(client, "قارن لي بين أرخص اتنين", conversation_id=first["conversation_id"])
    history_text = " ".join(m.content for m in llm.sent[-1][0])
    for p in first["products"]:
        assert f"id {p['id']} =" in history_text
    assert "never show or quote" in history_text
    # and the note is for the model only: the stored reply the user sees is untouched
    assert "Internal note" not in first["reply"]
