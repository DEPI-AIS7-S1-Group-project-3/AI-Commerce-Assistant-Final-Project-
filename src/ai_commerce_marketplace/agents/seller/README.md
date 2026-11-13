# Seller Agent

Read-only analytics assistant for a store owner. It answers questions about the owner's own store
(sales, period comparison, top products, low stock, returns, product reviews) using real numbers.

## Rules (from the Agents guide)

- Calls `services/seller_analytics` only. No SQL, no models, no write access.
- `seller_id` comes from the token via `ToolContext`. The model never sees it and cannot pass it
  (`forbidden_argument`).
- Every number comes from a tool result, never from the model.
- Empty results (`empty: true`) and errors (`ok: false`) are returned as data; the agent says so and does not guess.
- It never explains why sales dropped by guessing; it shows what the numbers show.

## Files

| File | Purpose |
|---|---|
| `tools.py` | 7 tools, `REGISTRY`, and `call_tool()` (single entry point) |
| `prompts.py` | `build_system_prompt(today)`: Egyptian Arabic rules and date ranges |
| `eval/questions.json` | 15 questions with expected answers |
| `graph.py` | not built yet (waiting for the router / LangGraph decision) |

## Tools

| Tool | Params | Returns |
|---|---|---|
| `get_sales_summary` | `date_from`, `date_to` | revenue, units_sold, orders_count, aov |
| `compare_periods` | `a_from`, `a_to`, `b_from`, `b_to` | delta and change_pct per metric (`null` if baseline is 0) |
| `top_products` | `date_from`, `date_to`, `limit`, `worst` | best/worst sellers |
| `low_stock_products` | `threshold` | active products at or below threshold |
| `orders_by_status` | `date_from`, `date_to` | count per status |
| `returns_report` | `date_from`, `date_to` | total and by reason (rejected excluded) |
| `get_product_reviews` | `product_id` | rating avg, count, recent low-rated reviews |

Dates are ISO (`2026-10-06`), end exclusive, at most 366 days. `limit` is capped at 20.
Metric definitions: [docs/seller-metrics.md](../../../../docs/seller-metrics.md).

## Try it

```python
from ai_commerce_marketplace.agents.seller.tools import ToolContext, call_tool
from ai_commerce_marketplace.database.session import SessionLocal

with SessionLocal() as s:
    ctx = ToolContext(session=s, seller_id=1)
    print(call_tool(ctx, "get_sales_summary", {"date_from": "2026-10-06", "date_to": "2026-11-05"}))
```

## Tests and eval

```bash
make test    # unit and integration tests for the tools
```

The eval runs the 15 questions through `call_tool` on the dev database and compares them to numbers
computed independently with SQL. It needs frozen data:

```bash
uv run alembic downgrade base && uv run alembic upgrade head
uv run python -m scripts.seed_database --anchor-date 2026-11-04T12:00:00
make test
```

If the dev database is not seeded with that anchor, the eval tests skip themselves.
