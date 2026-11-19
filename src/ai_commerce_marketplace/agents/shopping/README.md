# Shopping Agent

Read-only agent that helps a customer find, compare and choose products.
Every price, spec and rating must come from a tool result, never from the LLM.

## Status

| Piece | State |
|---|---|
| `schemas.py` | Done: `ProductCard` (search results), `ProductDetail` (details and compare) |
| `tools.py` | Done: 5 tools registered (see below) |
| `prompts.py` | Done: rules for search and filters, compare, recommend, prices and policies |
| `graph.py` | Not built yet (waiting for the router / LangGraph decision) |
| `eval/` | Not built yet (15-question set, same as the Seller agent) |

## Tools

| Tool | Owner | What it does | Parameters the LLM may fill |
|---|---|---|---|
| `search_products` | Person A | Search with filters and sort, returns `ProductCard` list | `query`, `category`, `brand`, `min_price`, `max_price`, `in_stock_only`, `sort`, `sort_spec`, `specs`, `limit` |
| `categories_brands_list` | Person A | Categories (with `spec_kind`) and brands with their slugs | none |
| `product_get` | Person B | Full details of one product | `product_id` |
| `products_compare` | Person B | Compare 2 to 4 products of the same category | `product_ids` |
| `reviews_summary_get` | Person B | Rating average, distribution and real review excerpts | `product_id` |

`customer_id` is never a parameter. `call_tool` rejects it (and any other extra argument) with `forbidden_argument`.

## Where the logic lives

Tools stay thin. The work is in `services/`:

| Service | Used by |
|---|---|
| `services/catalog.py` (website catalog, `list_products`, `list_categories`, `list_brands`) | `search_products`, `categories_brands_list` |
| `services/catalog_search.py` (maps listing results to `ProductCard`) | `search_products` |
| `services/catalog_details.py` (`get_product`, `compare_products`, `reviews_summary`) | `product_get`, `products_compare`, `reviews_summary_get` |

## Search filters

`search_products` takes the usual filters (category and brand slugs, price range, in-stock, sort) plus a `specs` object.
Only these spec keys are allowed. Anything else is rejected with `invalid_spec_filter`:

- **Minimum (`<key>_min`)**: `ram_gb`, `storage_gb`, `battery_mah`, `battery_hours`, `camera_mp`, `screen_inch`
- **Exact text**: `network` (`4g` / `5g`), `os`, `storage_type`, `type`, `connector`
- **Exact true/false**: `wireless`, `noise_cancelling`
- **`sort_spec`**: sorts high to low by one of the minimum keys without the suffix (for example `battery_mah`). Products without that spec go last.

CPU and GPU are free text and have no filter. They go into `query`.

## Rules

- Tools call `services/` only, never SQL directly.
- Inactive products are never listed. Out-of-stock products are hidden by default (`in_stock_only=true`) and shown with `in_stock=false` only when asked.
- `product_get` still returns an inactive or out-of-stock product (with `in_stock=false`) so the agent can say "not available now".
- Tools return `{"ok": ..., "empty": ...}` so the agent can say "no results" honestly and never guess.

## Run the tests

    uv run pytest tests/unit/test_shopping_tools.py tests/unit/test_shopping_prompts.py -q
    uv run pytest tests/integration/test_shopping_search.py tests/integration/test_shopping_details.py tests/integration/test_catalog_spec_filters.py -q

The integration tests need PostgreSQL (the `ai_commerce_test` database).
