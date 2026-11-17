# API Contracts

All money values are strings in EGP with 2 decimals (e.g. `"2060.00"`). Timestamps are ISO 8601 UTC.
Auth: `Authorization: Bearer <token>`. Identity (`customer_id`) always comes from the token, never from the body.
Every response carries an `X-Request-ID` header.

## Error shape

Every error returns:

```json
{ "code": "not_found", "message": "Route not found", "details": null }
```

| Status | Meaning |
|---|---|
| 400 | Business rule rejected (e.g. `cart_empty`, `insufficient_stock`) |
| 401 | Missing/invalid token (`unauthorized`, `invalid_token`, `invalid_credentials`) |
| 403 | Wrong role (`forbidden`) |
| 404 | Not found, or not yours (`*_not_found`) |
| 409 | Conflict with current state (`email_taken`, `checkout_unavailable`, `invalid_transition`, cancel/return codes) |
| 422 | Validation error. `details` = list of `{loc, msg, type}` |
| 500 | `internal_error`, no internals leaked |

## Auth

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/auth/register` | `full_name, email, phone, password` | 201 `UserOut` (customers only) |
| POST | `/auth/login` | `email, password` | 200 `{access_token, token_type}` |
| GET | `/auth/me` | | 200 `UserOut {id, role, full_name, email, phone}` |

Password: at least 8 chars with letters and digits. Phone: Egyptian mobile `01[0125]xxxxxxxx`.

## Addresses (customer)

| Method | Path | Notes |
|---|---|---|
| GET | `/addresses` | default first |
| POST | `/addresses` | first address becomes default |
| PUT | `/addresses/{id}` | full replace |
| POST | `/addresses/{id}/default` | switches default |
| DELETE | `/addresses/{id}` | 204; deleting the default promotes the newest |

Body: `label?, recipient_name, phone, governorate, city, street_address, is_default?`.

## Cart (customer)

| Method | Path | Body |
|---|---|---|
| GET | `/cart` | |
| POST | `/cart/items` | `{product_id, qty}` merges into one line |
| PUT | `/cart/items/{product_id}` | `{qty}` |
| DELETE | `/cart/items/{product_id}` | |
| DELETE | `/cart` | |

Response: `{items: [{product_id, title_ar, qty, unit_price_egp, line_total_egp, stock_qty, available}], subtotal_egp}`.
`available=false` lines are excluded from `subtotal_egp`. Errors: `insufficient_stock` (400, `details.available`), `product_not_found` (404).

## Orders (customer)

| Method | Path | Notes |
|---|---|---|
| POST | `/orders` | body `{address_id, payment_method: cod|wallet|card}` |
| GET | `/orders` | own orders, newest first |
| GET | `/orders/{id}` | adds `timeline: [{from_status, to_status, actor_type, created_at}]` |
| POST | `/orders/{id}/cancel` | returns order detail |
| POST | `/orders/{id}/items/{item_id}/return` | body `{reason_code, reason_text?}`, 201 |

`POST /orders` returns `{checkout_group_id, orders: [OrderOut]}`: one order per seller. Shipping: 60 EGP per order, free from 5000 EGP. `cod` -> `payment_status=pending`; wallet/card (simulated) -> `paid`.
Checkout failures: `cart_empty` (400), `address_not_found` (404), `checkout_unavailable` (409, `details` = list of `{product_id, reason, available?}`).

### Order statuses

`pending -> confirmed -> shipped -> out_for_delivery -> delivered -> return_requested -> returned`; `cancelled` from `pending` or `confirmed`.

### Cancel / return rules (409 codes)

| Code | Meaning |
|---|---|
| `already_shipped`, `already_delivered`, `already_cancelled`, `already_returned` | cancel rejected |
| `not_delivered`, `not_returnable`, `return_exists`, `window_expired` | return rejected |

Return window: 14 days from delivery (day 14 accepted, day 15 rejected). Return reasons: `defective, not_as_described, changed_mind, wrong_item, damaged_in_shipping, other`.

## Reviews

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/products/{id}/reviews?limit=10&offset=0` | public | `{product_id, rating_avg, rating_count, distribution: {"1".."5": n}, total, reviews: [ReviewOut]}`, newest first, `limit` 1..50 |
| POST | `/reviews` | customer | body `{order_item_id, rating: 1..5, body?: max 2000}` -> 201 `ReviewOut` |
| GET | `/reviews/mine` | customer | the customer's reviews |
| GET | `/reviews/reviewable` | customer | delivered items not reviewed yet: `[{order_id, order_item_id, product_id, title, delivered_at}]` |

`ReviewOut`: `{id, product_id, order_item_id, rating, body, author_name (first name only), is_verified_purchase, created_at}`.
Only the buyer can review, only after delivery (returned items too), once per order item. Writing a
review updates `products.rating_avg/rating_count` and `sellers.rating`.
Errors: `order_item_not_found` (404, also for someone else's item), `not_delivered` (409),
`review_exists` (409), `product_not_found` (404), sellers get `forbidden` (403).

## Policies (public, no login)

| Method | Path | Success |
|---|---|---|
| GET | `/policies` | 200 `[{slug, category, title_ar, version}]` in page order: shipping, returns, warranty, cancellation |
| GET | `/policies/{slug}` | 200 `{slug, category, title_ar, version, body_md, sections: [{no, title, body}]}` (current version) |

`body_md` is Markdown; `sections` are its numbered `## n.` headings (for a table of contents and for RAG).
Unknown slug: `policy_not_found` (404).

## Health

`GET /health` -> `{status: "ok", version}`.
