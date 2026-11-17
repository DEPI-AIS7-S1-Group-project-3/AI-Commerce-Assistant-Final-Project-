import type { CheckoutResult, Order, OrderDetail, PaymentMethod, ReturnReason } from "@/types";
import { getToken } from "@/hooks/useAuth";
import { http } from "./config";

const auth = () => ({ Authorization: `Bearer ${getToken() ?? ""}` });

// Backend Decimals arrive as strings: convert money fields once, here.
type Dec = string | number;
type ApiItem = Omit<Order["items"][number], "unit_price_egp" | "line_total_egp"> & { unit_price_egp: Dec; line_total_egp: Dec };
type ApiOrder = Omit<Order, "subtotal_egp" | "shipping_fee_egp" | "total_egp" | "items"> & {
  subtotal_egp: Dec;
  shipping_fee_egp: Dec;
  total_egp: Dec;
  items: ApiItem[];
};

export function fromApiOrder(o: ApiOrder): Order {
  return {
    ...o,
    subtotal_egp: Number(o.subtotal_egp),
    shipping_fee_egp: Number(o.shipping_fee_egp),
    total_egp: Number(o.total_egp),
    items: o.items.map((i) => ({ ...i, unit_price_egp: Number(i.unit_price_egp), line_total_egp: Number(i.line_total_egp) })),
  };
}

/** POST /orders: checks out the whole server cart, one order per seller. Clears the cart. */
export async function checkout(address_id: number, payment_method: PaymentMethod): Promise<CheckoutResult> {
  const r = await http<{ checkout_group_id: string; orders: ApiOrder[] }>("/orders", {
    method: "POST",
    headers: auth(),
    body: JSON.stringify({ address_id, payment_method }),
  });
  return { checkout_group_id: r.checkout_group_id, orders: r.orders.map(fromApiOrder) };
}

/** GET /orders: newest first. */
export async function listOrders(): Promise<Order[]> {
  return (await http<ApiOrder[]>("/orders", { headers: auth() })).map(fromApiOrder);
}

/** GET /orders/{id}: one order (= one package) with its status timeline. */
export async function getOrder(id: number): Promise<OrderDetail> {
  const o = await http<ApiOrder & { timeline: OrderDetail["timeline"] }>(`/orders/${id}`, { headers: auth() });
  return { ...fromApiOrder(o), timeline: o.timeline };
}

export const cancelOrder = (id: number) => http<unknown>(`/orders/${id}/cancel`, { method: "POST", headers: auth() });

export const requestReturn = (orderId: number, itemId: number, reason_code: ReturnReason, reason_text: string | null) =>
  http<unknown>(`/orders/${orderId}/items/${itemId}/return`, {
    method: "POST",
    headers: auth(),
    body: JSON.stringify({ reason_code, reason_text }),
  });
