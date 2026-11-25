"""The assistant graph: one chat message in, one reply out.

    prepare -> confirm -> (reply ready?) -> route -> agent -> guard -> persist

LangGraph is used for the control flow only. Every LLM call goes through our own ``llm``
client, so provider switching and fallback keep working. Identity is built here from the
authenticated user and passed to the agents as a ``ToolContext``; the model never sees it.

``handle_chat`` is the only function the API calls.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents import runner
from ai_commerce_marketplace.agents.catalog import AGENTS
from ai_commerce_marketplace.agents.order_actions import tools as oa_tools
from ai_commerce_marketplace.agents.router import guards, store
from ai_commerce_marketplace.agents.router.classify import classify
from ai_commerce_marketplace.agents.router.confirm import is_yes
from ai_commerce_marketplace.agents.router.rules import Agent, Role, route
from ai_commerce_marketplace.agents.seller import tools as seller_tools
from ai_commerce_marketplace.agents.shopping import tools as shopping_tools
from ai_commerce_marketplace.agents.support import tools as support_tools
from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.database.models.conversation import Conversation
from ai_commerce_marketplace.database.models.seller import Seller
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.llm import LLMClient, Message

CARD_TOOLS = {"search_products", "products_compare", "product_get"}
REJECTED = "Message must be 1 to 2000 characters"


class EmptyMessageError(AppError):
    status_code = 422
    code = "invalid_message"
    message = REJECTED


@dataclass(frozen=True)
class ChatResult:
    conversation_id: str
    reply: str
    agent: str
    products: list[dict[str, Any]] = field(default_factory=list)
    needs_confirmation: dict[str, str] | None = None
    trace: dict[str, Any] = field(default_factory=dict)


class State(TypedDict, total=False):
    message: str
    conv: Conversation
    history: list[Message]
    role: Role
    agent: Agent
    reply: str | None
    products: list[dict[str, Any]]
    needs_confirmation: dict[str, str] | None
    trace: dict[str, Any]
    tool_results: list[tuple[str, dict[str, Any]]]
    action_done: bool


def role_of(user: User | None) -> Role:
    if user is None:
        return "visitor"
    return "seller" if user.role == "seller" else "customer"


def _context(session: Session, user: User | None, agent: Agent) -> Any:
    """Build the agent's ToolContext from the authenticated user. Never from the model."""
    if agent == "seller":
        seller_id = (
            session.scalar(select(Seller.id).where(Seller.user_id == user.id)) if user else None
        )
        return seller_tools.ToolContext(session=session, seller_id=seller_id or -1)
    customer_id = user.id if user is not None else None
    if agent == "order_actions":
        return oa_tools.ToolContext(session=session, customer_id=customer_id or -1)
    if agent == "support":
        return support_tools.ToolContext(session=session, customer_id=customer_id)
    return shopping_tools.ToolContext(session=session, customer_id=customer_id)


def build_graph(session: Session, llm: LLMClient, user: User | None, now: datetime):
    tool_names = {n for spec in AGENTS.values() for n in spec.registry}

    def prepare(state: State) -> State:
        conv = state["conv"]
        return {"history": store.history(session, conv), "trace": state.get("trace", {})}

    def confirm(state: State) -> State:
        conv = state["conv"]
        pending = store.live_pending(conv, now)
        if pending is None:
            return {}
        store.clear_pending(conv)  # one try: a yes runs it, anything else drops it
        if not is_yes(state["message"]):
            return {}
        # Only a customer can have a pending action, and only in their own conversation.
        ctx = oa_tools.ToolContext(session=session, customer_id=conv.user_id or -1)
        result = oa_tools.execute_confirmed(ctx, pending)
        reply = str(result.get("message_ar") or guards.LEAK_REPLACEMENT)
        trace = {
            **state["trace"],
            "confirmation": {
                "tool": pending.get("tool"),
                "ok": result.get("ok"),
                "done": result.get("done", False),
            },
        }
        return {
            "reply": reply,
            "agent": "order_actions",
            "action_done": bool(result.get("done")),
            "tool_results": [("execute_confirmed", result)],
            "trace": trace,
        }

    def after_confirm(state: State) -> str:
        return "guard" if state.get("reply") else "route"

    def pick(state: State) -> State:
        conv = state["conv"]
        role = state["role"]
        last: Agent | None = conv.last_agent  # type: ignore[assignment]
        decision = route(state["message"], role, last)
        trace = dict(state["trace"])
        if decision is not None:
            trace["route"] = {
                "agent": decision.agent,
                "by": decision.reason,
                "detail": decision.detail,
            }
            return {"agent": decision.agent, "trace": trace}
        agent, resp = classify(llm, state["message"], role, last)
        chosen: Agent = agent or ("shopping" if role != "seller" else "seller")
        trace["route"] = {
            "agent": chosen,
            "by": "llm" if agent else "default",
            "provider": resp.provider,
        }
        return {"agent": chosen, "trace": trace}

    def run(state: State) -> State:
        agent = state["agent"]
        ctx = _context(session, user, agent)
        result = runner.run_agent(
            llm, AGENTS[agent], ctx, state["message"], state["history"], today=now.date()
        )
        products: list[dict[str, Any]] = []
        needs: dict[str, str] | None = None
        reply = result.reply
        for name, res in result.tool_results:
            if name in CARD_TOOLS and res.get("ok"):
                products = list(res.get("products") or res.get("items") or products)
            if res.get("needs_confirmation") and res.get("pending_action"):
                store.set_pending(state["conv"], res["pending_action"], now)
                question = str(res.get("confirm_question_ar") or "")
                needs = {"question": question}
                reply = question or reply  # a fixed question, not the model's wording
        trace = {
            **state["trace"],
            "tools": [
                {"tool": t.tool, "args": t.arguments, "ok": t.ok, "error": t.error, "ms": t.ms}
                for t in result.trace
            ],
            "rounds": result.rounds,
            "finish": result.finish,
            "provider": result.provider,
            "model": result.model,
            "failed_providers": list(result.failed_providers),
            "tokens": {"in": result.usage.input_tokens, "out": result.usage.output_tokens},
        }
        return {
            "reply": reply,
            "products": products,
            "needs_confirmation": needs,
            "tool_results": list(result.tool_results),
            "trace": trace,
        }

    def guard(state: State) -> State:
        reply, report = guards.check_reply(
            state["reply"] or "",
            state.get("tool_results", []),
            state["message"],
            tool_names,
            state.get("action_done", False),
        )
        trace = {
            **state["trace"],
            "guard": {
                "leaked": report.leaked,
                "false_action_claim": report.false_action_claim,
                "unsupported_numbers": report.unsupported_numbers,
                "jailbreak_pattern": guards.looks_like_jailbreak(state["message"]),
            },
        }
        update: State = {"reply": reply, "trace": trace}
        if report.changed:
            update["products"] = []
            update["needs_confirmation"] = None
            store.clear_pending(state["conv"])
        return update

    def persist(state: State) -> State:
        store.add_turn(
            session,
            state["conv"],
            state["message"],
            state["reply"] or "",
            state["agent"],
            [state["trace"]],
        )
        return {}

    g = StateGraph(State)
    g.add_node("prepare", prepare)
    g.add_node("confirm", confirm)
    g.add_node("route", pick)
    g.add_node("agent", run)
    g.add_node("guard", guard)
    g.add_node("persist", persist)
    g.set_entry_point("prepare")
    g.add_edge("prepare", "confirm")
    g.add_conditional_edges("confirm", after_confirm, {"guard": "guard", "route": "route"})
    g.add_edge("route", "agent")
    g.add_edge("agent", "guard")
    g.add_edge("guard", "persist")
    g.add_edge("persist", END)
    return g.compile()


def handle_chat(
    session: Session,
    llm: LLMClient,
    user: User | None,
    message: str,
    conversation_id: str | None = None,
    now: datetime | None = None,
) -> ChatResult:
    """Answer one chat message. LLM failures propagate; the API turns them into a 503."""
    text = guards.clean_message(message)
    if not text or len(text) > guards.MAX_MESSAGE_CHARS:
        raise EmptyMessageError()
    now = now or datetime.now(UTC)
    role = role_of(user)
    conv = store.open_conversation(session, conversation_id, user.id if user else None, role)
    graph = build_graph(session, llm, user, now)
    out = graph.invoke({"message": text, "conv": conv, "role": role, "trace": {}})
    return ChatResult(
        conversation_id=str(conv.id),
        reply=out["reply"] or "",
        agent=out["agent"],
        products=out.get("products", []),
        needs_confirmation=out.get("needs_confirmation"),
        trace=out["trace"],
    )


__all__ = ["ChatResult", "EmptyMessageError", "build_graph", "handle_chat", "role_of"]
