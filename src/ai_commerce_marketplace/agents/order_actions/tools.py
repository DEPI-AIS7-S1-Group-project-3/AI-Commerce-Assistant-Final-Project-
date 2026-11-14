"""Tools for the Order Actions Agent.

Two kinds of tools:

- Read tools (list_my_orders, get_order, check_*_eligibility) run directly.
- Action tools (cancel_order, request_return) NEVER change data from call_tool. call_tool only
  checks eligibility and returns a `pending_action` plus a ready confirmation question. The router
  keeps the pending action and, only after the user explicitly says yes, runs it with
  execute_confirmed(). The LLM has no way to call execute_confirmed.

Eligibility is decided by the pure rules in services/order_rules.py (through services), never by
the model. customer_id comes from the token via ToolContext; the model cannot pass it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import ActorType, CancelReason, OrderStatus, ReturnReason
from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.schemas.order import OrderOut
from ai_commerce_marketplace.services import order_actions as actions_svc
from ai_commerce_marketplace.services import orders as orders_svc
from ai_commerce_marketplace.services.order_rules import RETURN_WINDOW_DAYS

MAX_LIMIT = 20
MAX_REASON_TEXT = 500

# Reasons a customer may give for cancelling (the rest are for sellers/system).
CUSTOMER_CANCEL_REASONS = (
    CancelReason.CUSTOMER_REQUEST,
    CancelReason.LATE_DELIVERY,
    CancelReason.OTHER,
)

STATUS_AR: dict[str, str] = {
    OrderStatus.PENDING: "قيد المراجعة",
    OrderStatus.CONFIRMED: "اتأكد ومستني الشحن",
    OrderStatus.SHIPPED: "اتشحن",
    OrderStatus.OUT_FOR_DELIVERY: "خرج للتوصيل",
    OrderStatus.DELIVERED: "اتسلّم",
    OrderStatus.CANCELLED: "اتلغى",
    OrderStatus.RETURN_REQUESTED: "عليه طلب إرجاع",
    OrderStatus.RETURNED: "اترجع",
}

PAYMENT_AR = {"cod": "الدفع عند الاستلام", "wallet": "محفظة", "card": "كارت"}

RETURN_REASON_AR: dict[str, str] = {
    ReturnReason.DEFECTIVE: "المنتج فيه عيب",
    ReturnReason.NOT_AS_DESCRIBED: "المنتج مش زي الوصف",
    ReturnReason.CHANGED_MIND: "غيّرت رأيي",
    ReturnReason.WRONG_ITEM: "وصلني منتج غلط",
    ReturnReason.DAMAGED_IN_SHIPPING: "المنتج اتضرر في الشحن",
    ReturnReason.OTHER: "سبب تاني",
}

CANCEL_REASON_AR: dict[str, str] = {
    CancelReason.CUSTOMER_REQUEST: "طلب العميل",
    CancelReason.LATE_DELIVERY: "التأخير في التوصيل",
    CancelReason.OTHER: "سبب تاني",
}

# Arabic text for every code a tool can return. The model shows these, it does not invent them.
MESSAGES_AR = {
    "cancel_ok": "الطلب ينفع يتلغي.",
    "return_ok": "المنتج ينفع يترجع.",
    "already_cancelled": "الطلب ده متلغي بالفعل.",
    "already_returned": "الطلب ده عليه إرجاع بالفعل، فمينفعش يتلغي.",
    "already_delivered": (
        "الطلب اتسلّم خلاص فمينفعش يتلغي. لو لسه في خلال 14 يوم من الاستلام "
        "ممكن تطلب إرجاع بدل الإلغاء."
    ),
    "already_shipped": (
        "الطلب اتشحن خلاص، والإلغاء متاح بس قبل الشحن. "
        "أول ما يوصلك تقدر تطلب إرجاع خلال 14 يوم من الاستلام."
    ),
    "not_delivered": "الإرجاع متاح بس للطلبات اللي اتسلّمت.",
    "not_returnable": "المنتج ده مش قابل للإرجاع.",
    "return_exists": "فيه طلب إرجاع مفتوح بالفعل للمنتج ده.",
    "window_expired": "مدة الإرجاع (14 يوم من الاستلام) خلصت.",
    "invalid_qty": "الكمية لازم تكون من 1 لحد الكمية اللي اشتريتها.",
    "order_not_found": "مش لاقي طلب بالرقم ده في حسابك.",
    "order_item_not_found": "المنتج ده مش موجود في الطلب ده.",
    "invalid_transition": "حالة الطلب اتغيرت، ومينفعش أنفذ الإجراء ده دلوقتي.",
    "invalid_order_id": "رقم الطلب لازم يكون رقم صحيح.",
    "invalid_item_id": "رقم المنتج في الطلب لازم يكون رقم صحيح.",
    "invalid_status": "حالة الطلب المطلوبة مش معروفة.",
    "invalid_limit": "العدد لازم يكون رقم صحيح أكبر من صفر.",
    "invalid_reason": "سبب مش معروف.",
    "reason_text_too_long": "وصف السبب طويل زيادة.",
    "unknown_tool": "حصلت مشكلة داخلية.",
    "forbidden_argument": "الطلب ده فيه بيانات مش مسموح بيها.",
    "bad_arguments": "البيانات ناقصة أو غلط.",
    "not_an_action": "الإجراء ده مش معروف.",
}
GENERIC_ERROR_AR = "حصلت مشكلة ومقدرتش أكمّل الطلب ده."


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    customer_id: int
    now: datetime | None = None  # only tests/eval set this; production uses the real clock


class ToolInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _ar(code: str) -> str:
    return MESSAGES_AR.get(code, GENERIC_ERROR_AR)


def _now(ctx: ToolContext) -> datetime:
    return ctx.now or datetime.now(UTC)


def _safe(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run a tool body and always return a dict (never raise to the agent)."""
    try:
        return {"ok": True, **fn()}
    except ToolInputError as e:
        return {"ok": False, "error": e.code, "message": str(e), "message_ar": _ar(e.code)}
    except AppError as e:
        return {"ok": False, "error": e.code, "message": e.message, "message_ar": _ar(e.code)}


# ---- input checks ----
def _pos_int(value: Any, code: str, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ToolInputError(code, f"{name} must be a positive integer")
    return value


def _qty(value: Any) -> int | None:
    return None if value is None else _pos_int(value, "invalid_qty", "qty")


def _cancel_reason(value: Any) -> str:
    if value not in CUSTOMER_CANCEL_REASONS:
        allowed = [str(r) for r in CUSTOMER_CANCEL_REASONS]
        raise ToolInputError("invalid_reason", f"reason_code must be one of {allowed}")
    return str(value)


def _return_reason(value: Any) -> str:
    if value not in list(ReturnReason):
        raise ToolInputError(
            "invalid_reason", f"reason_code must be one of {[str(r) for r in ReturnReason]}"
        )
    return str(value)


def _reason_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_REASON_TEXT:
        raise ToolInputError(
            "reason_text_too_long", f"reason_text must be text of at most {MAX_REASON_TEXT}"
        )
    return value.strip() or None


# ---- output shaping (all numbers come from the database) ----
def _order_view(order: OrderOut, now: datetime) -> dict[str, Any]:
    d = order.model_dump(mode="json", exclude={"seller_id", "shipping_address"})
    # the model only needs where it goes, not the phone or street
    addr = order.shipping_address or {}
    d["ship_to"] = {"governorate": addr.get("governorate"), "city": addr.get("city")}
    d["status_ar"] = STATUS_AR.get(order.status, order.status)
    d["payment_method_ar"] = PAYMENT_AR.get(order.payment_method, order.payment_method)
    for item in d["items"]:
        item["order_item_id"] = item.pop("id")
    if order.delivered_at is not None:
        deadline = order.delivered_at + timedelta(days=RETURN_WINDOW_DAYS)
        d["return_deadline"] = deadline.isoformat()
        d["days_since_delivery"] = (now - order.delivered_at).days
    in_transit = order.status in {
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        OrderStatus.SHIPPED,
        OrderStatus.OUT_FOR_DELIVERY,
    }
    d["days_late"] = (
        (now - order.expected_delivery_at).days
        if in_transit and now > order.expected_delivery_at
        else 0
    )
    return d


def _find_item(order: dict[str, Any], order_item_id: int) -> dict[str, Any]:
    for item in order["items"]:
        if item["order_item_id"] == order_item_id:
            return item
    raise AppError("Order item not found", code="order_item_not_found")


def _load_order(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    detail = orders_svc.get_order(ctx.session, ctx.customer_id, order_id)
    view = _order_view(detail, _now(ctx))
    for step in view["timeline"]:
        step["to_status_ar"] = STATUS_AR.get(step["to_status"], step["to_status"])
    return view


# ---- read tools ----
def list_my_orders(ctx: ToolContext, status: str | None = None, limit: int = 10) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        if status is not None and status not in list(OrderStatus):
            raise ToolInputError(
                "invalid_status", f"status must be one of {[str(s) for s in OrderStatus]}"
            )
        n = min(_pos_int(limit, "invalid_limit", "limit"), MAX_LIMIT)
        now = _now(ctx)
        rows = [
            _order_view(o, now)
            for o in orders_svc.list_orders(ctx.session, ctx.customer_id)
            if status is None or o.status == status
        ]
        return {"orders": rows[:n], "total": len(rows), "empty": not rows}

    return _safe(run)


def get_order(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        return {"order": _load_order(ctx, _pos_int(order_id, "invalid_order_id", "order_id"))}

    return _safe(run)


def _cancel_check(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    order_id = _pos_int(order_id, "invalid_order_id", "order_id")
    v = actions_svc.get_cancel_eligibility(ctx.session, ctx.customer_id, order_id, now=ctx.now)
    result: dict[str, Any] = {
        "order_id": order_id,
        "allowed": v.allowed,
        "reason_code": v.code,
        "message_ar": _ar("cancel_ok" if v.allowed else v.code),
        "order": _load_order(ctx, order_id),
    }
    if v.code == "already_delivered":
        result["alternative"] = "return"  # suggest checking return eligibility instead
    return result


def check_cancel_eligibility(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    return _safe(lambda: _cancel_check(ctx, order_id))


def _return_check(
    ctx: ToolContext, order_id: int, order_item_id: int, qty: int | None
) -> dict[str, Any]:
    order_id = _pos_int(order_id, "invalid_order_id", "order_id")
    order_item_id = _pos_int(order_item_id, "invalid_item_id", "order_item_id")
    qty = _qty(qty)
    v = actions_svc.get_return_eligibility(
        ctx.session, ctx.customer_id, order_id, order_item_id, qty, now=ctx.now
    )
    order = _load_order(ctx, order_id)
    item = _find_item(order, order_item_id)
    return {
        "order_id": order_id,
        "order_item_id": order_item_id,
        "qty": item["qty"] if qty is None else qty,
        "max_qty": item["qty"],
        "allowed": v.allowed,
        "reason_code": v.code,
        "message_ar": _ar("return_ok" if v.allowed else v.code),
        "item": item,
        "delivered_at": order["delivered_at"],
        "return_deadline": order.get("return_deadline"),
        "days_since_delivery": order.get("days_since_delivery"),
    }


def check_return_eligibility(
    ctx: ToolContext, order_id: int, order_item_id: int, qty: int | None = None
) -> dict[str, Any]:
    return _safe(lambda: _return_check(ctx, order_id, order_item_id, qty))


# ---- action tools: propose (via call_tool) and execute (via execute_confirmed) ----
def _pending(tool: str, args: dict[str, Any], question_ar: str) -> dict[str, Any]:
    return {
        "allowed": True,
        "needs_confirmation": True,
        "pending_action": {"tool": tool, "args": args},
        "confirm_question_ar": question_ar,
    }


def propose_cancel_order(
    ctx: ToolContext, order_id: int, reason_code: str = CancelReason.CUSTOMER_REQUEST
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        reason = _cancel_reason(reason_code)
        check = _cancel_check(ctx, order_id)
        if not check["allowed"]:
            return {**check, "needs_confirmation": False}
        o = check["order"]
        titles = "، ".join(i["title"] for i in o["items"])
        question = (
            f"هتلغي الطلب رقم {o['id']} ({titles}) بإجمالي {o['total_egp']} جنيه، "
            f"والسبب: {CANCEL_REASON_AR[CancelReason(reason)]}. متأكد؟ "
            "رد بـ «أيوه» عشان أنفذ أو «لأ» عشان نلغي العملية."
        )
        args = {"order_id": o["id"], "reason_code": reason}
        return {**_pending("cancel_order", args, question), "order": o}

    return _safe(run)


def execute_cancel_order(
    ctx: ToolContext, order_id: int, reason_code: str = CancelReason.CUSTOMER_REQUEST
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        oid = _pos_int(order_id, "invalid_order_id", "order_id")
        reason = _cancel_reason(reason_code)
        # the service re-checks eligibility with the order row locked
        actions_svc.cancel_order(
            ctx.session,
            ctx.customer_id,
            oid,
            actor_type=ActorType.AGENT,
            reason_code=reason,
            now=ctx.now,
        )
        order = _load_order(ctx, oid)
        return {
            "done": True,
            "order_id": oid,
            "status": order["status"],
            "status_ar": order["status_ar"],
            "payment_status": order["payment_status"],
            "stock_restored": True,
            "message_ar": f"تم إلغاء الطلب رقم {oid}.",
        }

    return _safe(run)


def propose_request_return(
    ctx: ToolContext,
    order_id: int,
    order_item_id: int,
    reason_code: str,
    qty: int | None = None,
    reason_text: str | None = None,
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        reason = _return_reason(reason_code)
        text = _reason_text(reason_text)
        check = _return_check(ctx, order_id, order_item_id, qty)
        if not check["allowed"]:
            return {**check, "needs_confirmation": False}
        question = (
            f"هتطلب إرجاع {check['qty']} من «{check['item']['title']}» "
            f"من الطلب رقم {check['order_id']}، والسبب: {RETURN_REASON_AR[ReturnReason(reason)]}. "
            "متأكد؟ رد بـ «أيوه» عشان أنفذ أو «لأ» عشان نلغي العملية."
        )
        args = {
            "order_id": check["order_id"],
            "order_item_id": check["order_item_id"],
            "qty": check["qty"],
            "reason_code": reason,
            "reason_text": text,
        }
        return {**_pending("request_return", args, question), "item": check["item"]}

    return _safe(run)


def execute_request_return(
    ctx: ToolContext,
    order_id: int,
    order_item_id: int,
    reason_code: str,
    qty: int | None = None,
    reason_text: str | None = None,
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        oid = _pos_int(order_id, "invalid_order_id", "order_id")
        iid = _pos_int(order_item_id, "invalid_item_id", "order_item_id")
        ret = actions_svc.request_return(
            ctx.session,
            ctx.customer_id,
            oid,
            iid,
            ReturnReason(_return_reason(reason_code)),
            _reason_text(reason_text),
            qty=_qty(qty),
            actor_type=ActorType.AGENT,
            now=ctx.now,
        )
        return {
            "done": True,
            "return_id": ret.id,
            "order_id": oid,
            "order_item_id": iid,
            "qty": ret.qty,
            "return_status": ret.status,
            "message_ar": (
                f"تم تسجيل طلب الإرجاع رقم {ret.id} للطلب رقم {oid}. البائع هيراجعه ويتواصل معاك."
            ),
        }

    return _safe(run)


# What the LLM may fill in. ctx is never listed here.
REGISTRY: dict[str, dict[str, Any]] = {
    "list_my_orders": {
        "fn": list_my_orders,
        "description": "The customer's orders, newest first, optionally filtered by status.",
        "params": ["status", "limit"],
    },
    "get_order": {
        "fn": get_order,
        "description": "One order of the customer: items, totals, status and its history.",
        "params": ["order_id"],
    },
    "check_cancel_eligibility": {
        "fn": check_cancel_eligibility,
        "description": "Check only: can this order be cancelled, and why not.",
        "params": ["order_id"],
    },
    "check_return_eligibility": {
        "fn": check_return_eligibility,
        "description": "Check only: can this item be returned (qty default = all bought).",
        "params": ["order_id", "order_item_id", "qty"],
    },
    "cancel_order": {
        "fn": propose_cancel_order,
        "execute": execute_cancel_order,
        "requires_confirmation": True,
        "description": (
            "Ask to cancel an order. Does not cancel: returns a confirmation question "
            "that must be shown to the customer."
        ),
        "params": ["order_id", "reason_code"],
    },
    "request_return": {
        "fn": propose_request_return,
        "execute": execute_request_return,
        "requires_confirmation": True,
        "description": (
            "Ask to return an item. Does not submit: returns a confirmation question "
            "that must be shown to the customer."
        ),
        "params": ["order_id", "order_item_id", "reason_code", "qty", "reason_text"],
    },
}


def _bad_args(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    spec = REGISTRY.get(name)
    if spec is None:
        code = "unknown_tool"
        return {
            "ok": False,
            "error": code,
            "message": f"No tool named {name}",
            "message_ar": _ar(code),
        }
    extra = set(args) - set(spec["params"])
    if extra:
        # e.g. the model tried to pass customer_id
        code = "forbidden_argument"
        return {
            "ok": False,
            "error": code,
            "message": f"Not allowed: {sorted(extra)}",
            "message_ar": _ar(code),
        }
    return None


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the LLM's tool calls. Never changes data."""
    error = _bad_args(name, args)
    if error:
        return error
    try:
        return REGISTRY[name]["fn"](ctx, **args)
    except TypeError:
        code = "bad_arguments"
        return {
            "ok": False,
            "error": code,
            "message": "Missing or wrong arguments",
            "message_ar": _ar(code),
        }


def execute_confirmed(ctx: ToolContext, pending_action: dict[str, Any]) -> dict[str, Any]:
    """Run a pending action. Only the router calls this, after the user explicitly said yes.

    pending_action is exactly what call_tool returned. Ownership and eligibility are checked
    again inside the service, so a stale or edited action cannot do harm.
    """
    name = pending_action.get("tool") if isinstance(pending_action, dict) else None
    args = pending_action.get("args") if isinstance(pending_action, dict) else None
    spec = REGISTRY.get(name) if isinstance(name, str) else None
    if spec is None or "execute" not in spec or not isinstance(args, dict):
        code = "not_an_action"
        return {
            "ok": False,
            "error": code,
            "message": "Not a pending action",
            "message_ar": _ar(code),
        }
    assert isinstance(name, str)
    error = _bad_args(name, args)
    if error:
        return error
    try:
        return spec["execute"](ctx, **args)
    except TypeError:
        code = "bad_arguments"
        return {
            "ok": False,
            "error": code,
            "message": "Missing or wrong arguments",
            "message_ar": _ar(code),
        }
