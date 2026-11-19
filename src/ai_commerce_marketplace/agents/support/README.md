# Support Agent

Answers customers' questions about **their own orders** and about the **store policies**
(shipping, returns, warranty, cancellation). It is **read-only**: it never cancels or returns
anything. Those actions belong to the Order Actions agent, after an explicit confirmation.

## Status

Tool layer only (this folder). The system prompt, the evaluation set and the graph come next.

## Rules

1. `customer_id` comes from `ToolContext` (the token). It is never a tool argument; passing it
   returns `forbidden_argument`.
2. An order that is not the customer's is reported as `order_not_found`, exactly like a
   missing order.
3. Tools never raise. They return `{"ok": true, ...}` or `{"ok": false, "error", "message"}`.
   An empty search is `empty: true`, not an error.
4. Every number and date comes from a service. Warranty end dates and cancel/return
   eligibility are computed in the backend, never by the model.
5. Policy tools are open to visitors. Order tools need a signed-in customer (`login_required`).

## Tools

| Tool | Purpose | Backed by |
|---|---|---|
| `policy_search(query, limit)` | Best policy sections for a question, each with slug, version and section number | `services/policy_search.py` |
| `policy_get(slug, section_no?)` | A whole policy or one numbered section | `services/policies.py` |
| `order_list(limit)` | The customer's latest orders | `services/orders.py` |
| `order_get(order_id)` | Status, items, expected delivery, timeline | `services/orders.py` |
| `order_eligibility(order_id)` | Can the order be cancelled; can each item be returned, and why not | `services/order_rules.py` through `orders.get_order` |
| `warranty_status(order_id)` | Warranty start, end and days left per item | `services/order_support.py` |
| `return_status(order_id)` | Return requests already made, with status | `services/order_support.py` |

Entry point: `call_tool(ctx, name, args)`. The shared checks (unknown tool, forbidden
arguments, bad arguments) live in `agents/common.py`.

## Policy search

The four policies are small (about 26 numbered sections), so retrieval is a plain keyword
match over sections, not embeddings: Arabic normalization (`nlp/arabic.py`), stopwords, the
definite article dropped, words that share the same consonants match (`ارجع` / `ارجاع` /
`بترجع`), rarer words weigh more, and a hit in a title counts extra. The function is pure
(`rank_sections`), so it is easy to test and easy to replace with embeddings later without
changing the tool contract.

## Try it

```python
from ai_commerce_marketplace.agents.support.tools import ToolContext, call_tool

ctx = ToolContext(session=session, customer_id=1)
call_tool(ctx, "policy_search", {"query": "اقدر ارجع السماعة الداخلية؟"})
call_tool(ctx, "order_eligibility", {"order_id": 10004})  # delivered 31 days ago -> window_expired
```
