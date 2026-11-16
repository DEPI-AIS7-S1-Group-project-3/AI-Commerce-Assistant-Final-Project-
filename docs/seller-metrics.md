# Seller metrics

All numbers are computed in SQL by `services/seller_analytics.py`. The agent never computes them.

## Scope
- Every function takes `seller_id` (`sellers.id`) resolved from the token. Never from user text.
- Period: `orders.created_at >= date_from AND orders.created_at < date_to` (start inclusive, end exclusive).

## Definitions
| Metric | Definition |
|---|---|
| counted orders | orders of the seller whose status is NOT `cancelled` and NOT `returned` |
| revenue | sum of `order_items.line_total_egp` of counted orders. Shipping excluded |
| units_sold | sum of `order_items.qty` of counted orders |
| orders_count | number of counted orders |
| AOV | revenue / orders_count (0.00 if no orders) |

`return_requested` orders are counted until they become `returned`.

## Comparison
`delta = b - a`, `change_pct = delta / a * 100` rounded to 1 decimal. `change_pct` is `null` when `a = 0`.
`period_a` is the earlier (baseline) period, `period_b` the later one.

## Stock
Low stock = active products with `stock_qty <= threshold` (0 means out of stock). Sorted by lowest stock.
