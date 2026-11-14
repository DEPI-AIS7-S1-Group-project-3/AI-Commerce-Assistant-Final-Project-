# Order Actions Agent

Handles a customer's orders: shows them with their history, cancels an order, or submits a return,
safely. It is the only agent that changes data, so accuracy matters more than speed.

## Rules (from the Agents guide)

- Calls `services/orders` and `services/order_actions` only. No SQL, no models.
- `customer_id` comes from the token via `ToolContext`. The model never sees it and cannot pass it
  (`forbidden_argument`).
- Eligibility is decided by the pure rules in `services/order_rules.py`, never by the model.
- Nothing changes without an explicit "yes" from the customer (see the flow below).
- Every change is written to `order_status_history` with `actor_type='agent'`.
- Another customer's order looks exactly like a missing one (`order_not_found`).
- Errors (`ok: false`) and refusals (`allowed: false`) come back as data with `message_ar`;
  the agent says them and does not guess.

## Files

| File | Purpose |
|---|---|
| `tools.py` | 6 tools, `REGISTRY`, `call_tool()` (for the LLM) and `execute_confirmed()` (for the router) |
| `prompts.py` | `build_system_prompt(today)`: Egyptian Arabic rules and the action flow |
| `eval/questions.json` | 15 questions with expected tool results and expected answers |
| `graph.py` | not built yet (waiting for the router / LangGraph decision, same as the Seller Agent) |

## Tools

| Tool | Params | Changes data? |
|---|---|---|
| `list_my_orders` | `status?`, `limit?` (max 20) | no |
| `get_order` | `order_id` | no (items with `order_item_id`, timeline, `days_late`, `return_deadline`) |
| `check_cancel_eligibility` | `order_id` | no → `allowed`, `reason_code`, `message_ar` |
| `check_return_eligibility` | `order_id`, `order_item_id`, `qty?` | no → `allowed`, `reason_code`, `message_ar`, deadline |
| `cancel_order` | `order_id`, `reason_code?` | **only after confirmation** |
| `request_return` | `order_id`, `order_item_id`, `reason_code`, `qty?`, `reason_text?` | **only after confirmation** |

`request_return` takes `order_id` too (the guide lists only `order_item_id`): the service checks
ownership through the order.

Cancel reasons: `customer_request`, `late_delivery`, `other`.
Return reasons: `defective`, `not_as_described`, `changed_mind`, `wrong_item`, `damaged_in_shipping`, `other`.

## The confirmation flow (contract with the router)

```text
customer: "ألغي طلب 10002"
  LLM  → call_tool(ctx, "cancel_order", {"order_id": 10002})
  tool → checks eligibility, changes NOTHING, returns:
         {"ok": true, "needs_confirmation": true,
          "pending_action": {"tool": "cancel_order", "args": {...}},
          "confirm_question_ar": "هتلغي الطلب رقم 10002 ... متأكد؟"}
  router → stores pending_action in session_state, shows confirm_question_ar, stops.
customer: "أيوه"
  router → execute_confirmed(ctx, pending_action)   # the LLM cannot call this
  tool   → service re-checks ownership + eligibility with the row locked, then cancels.
customer: anything else → router drops pending_action.
```

If the rule says no, the action tool returns `allowed: false`, `needs_confirmation: false` and no
`pending_action`. If the order changed between the question and the "yes" (e.g. the seller shipped
it), `execute_confirmed` returns the new refusal and changes nothing.

## Try it

```python
from ai_commerce_marketplace.agents.order_actions.tools import ToolContext, call_tool, execute_confirmed
from ai_commerce_marketplace.database.session import SessionLocal

with SessionLocal() as s:
    ctx = ToolContext(session=s, customer_id=5)          # customer01
    r = call_tool(ctx, "cancel_order", {"order_id": 10002})
    print(r["confirm_question_ar"])
    print(execute_confirmed(ctx, r["pending_action"]))   # really cancels on the dev DB
```

## Tests and eval

```bash
make test
```

- `tests/integration/test_order_actions_tools.py`: the tools (identity, flow, refusals).
- `tests/integration/test_order_eligibility.py`: the service additions the agent uses.
- `tests/integration/test_order_actions_eval.py`: the 15 questions on the demo orders 10001-10005
  and a few more. Each one runs in a rolled-back transaction, so the dev data is not changed. It needs
  the frozen seed, otherwise it skips itself:

```bash
uv run alembic downgrade base && uv run alembic upgrade head
uv run python -m scripts.seed_database --anchor-date 2026-11-04T12:00:00
make test
```

## Open decisions

- **D3**: cancelling a shipped order that is more than 3 days late is **not** allowed yet (the team
  has not approved it). Order 10001 is refused with `already_shipped`.
- **Refund on cancel**: the cancel service does not set `payment_status = refunded` for card/wallet
  orders yet. The agent never promises a refund unless `payment_status` is `refunded`.
