import type { Lang, TKey } from "@/lib/i18n";
import type { Order, OrderStatus } from "@/types";

const BLOCKS = new Set([
  "not_delivered", "not_returnable", "return_exists", "window_expired",
  "already_shipped", "already_delivered", "already_cancelled", "already_returned",
]);

/** Message key for a backend block/409 code; falls back to a generic error. */
export const blockKey = (code: string | null | undefined): TKey =>
  code && BLOCKS.has(code) ? (`blk.${code}` as TKey) : "ord.err.generic";

export const statusKey = (s: OrderStatus) => `st.${s}` as TKey;

/** Chip colour per status: green-ish for done, warn for in-progress problems, muted for cancelled. */
export const statusClass = (s: OrderStatus) =>
  s === "delivered" || s === "returned"
    ? "chip-neon"
    : s === "cancelled"
      ? "chip line-through"
      : s === "return_requested"
        ? "chip !border-warn !text-warn"
        : "chip";

export const fmtDate = (iso: string, lang: Lang, withDay = false) =>
  new Date(iso).toLocaleDateString(lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB", {
    ...(withDay ? { weekday: "long" } : {}),
    day: "numeric",
    month: "long",
    year: "numeric",
  });

/** Orders from one checkout (same checkout_group_id), newest purchase first. */
export function groupPurchases(orders: Order[]): Order[][] {
  const map = new Map<string, Order[]>();
  orders.forEach((o) => map.set(o.checkout_group_id, [...(map.get(o.checkout_group_id) ?? []), o]));
  return [...map.values()].map((g) => g.sort((a, b) => a.id - b.id));
}

export const RETURN_WINDOW_DAYS = 14;
