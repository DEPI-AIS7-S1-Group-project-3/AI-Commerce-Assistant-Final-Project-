# Shopping Agent

Read-only assistant that helps a customer find the right product for their budget and need, compare
products and recommend with a reason, using only real catalog data.

## Rules (from the Agents guide)

- Calls `services/` only (`catalog_details`, and `reviews` through it). No SQL or models in tools.
- Every price, spec and rating comes from a tool result, never from the model.
- Unavailable products (`is_active = false` or `stock_qty = 0`) come back with `in_stock: false`;
  the agent says "not available now" and never recommends them.
- No purchase and no checkout.
- Errors (`ok: false`) and empty results (`empty: true`) are returned as data; the agent says so and
  does not guess.
- `customer_id` comes from the token via `ToolContext`. The model never sees it and cannot pass it
  (`forbidden_argument`).

## Files

| File | Purpose |
|---|---|
| `tools.py` | tools, `REGISTRY`, `call_tool()` (single entry point, rejects unknown tools and extra args) |
| `schemas.py` | `ProductCard`, `ProductDetail` (shared return shapes) |
| `prompts.py` | `build_system_prompt(today)`: Egyptian Arabic rules for search, compare, recommend, reviews, prices |
| `graph.py` | not built yet (waiting for the team's agent runtime decision) |

## Tools

| Tool | Owner | Params | Returns |
|---|---|---|---|
| `product_get` | Person B | `product_id` | `product`: price, old price, specs, warranty, returnable, stock, `in_stock`, rating, images |
| `products_compare` | Person B | `product_ids` (2-4) | `products`, `spec_keys` (official keys for the category), `missing_ids` |
| `reviews_summary_get` | Person B | `product_id` | `rating_avg`, `rating_count`, 1-5 `distribution`, up to 5 `positive` and 5 `negative` review texts, `empty` |
| `search_products` | Person A | `query`, `filters`, `sort`, `limit` | not built yet (can reuse `services/catalog.list_products`) |
| `categories_brands_list` | Person A | none | not built yet |

Details:

- Ids may be numbers or digit strings (`"12"`); anything else is `invalid_product_id`.
- `products_compare`: duplicates are removed; unknown ids go to `missing_ids`; fewer than 2 found is
  `not_enough_products`; different categories is `mixed_categories`; not 2-4 ids is `invalid_ids_count`.
- Brand is the Arabic name, falling back to English. Prices and ratings are exact strings (`"9999.00"`).
- `reviews_summary_get` excerpts: newest non-empty reviews, 4-5 stars (positive) and 1-2 stars (negative),
  each trimmed to 300 characters. 3-star reviews count in the distribution only. The agent summarizes
  praise and complaints from these texts only.

## Try it

```python
from ai_commerce_marketplace.agents.shopping.tools import ToolContext, call_tool
from ai_commerce_marketplace.database.session import SessionLocal

with SessionLocal() as s:
    ctx = ToolContext(session=s)
    print(call_tool(ctx, "product_get", {"product_id": 1}))
    print(call_tool(ctx, "products_compare", {"product_ids": [1, 2]}))
    print(call_tool(ctx, "reviews_summary_get", {"product_id": 1}))
```

## Tests

```bash
uv run pytest tests/integration/test_shopping_details.py tests/unit/test_shopping_tools.py tests/unit/test_shopping_prompts.py -q
```

Covered: service results, tool shapes, id parsing, every error code, `customer_id` rejection, and that
the prompt keeps its key rules. Not built yet: an eval set like the Seller agent's.
