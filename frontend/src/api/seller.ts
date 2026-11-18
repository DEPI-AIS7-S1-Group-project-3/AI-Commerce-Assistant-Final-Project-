import type {
  OrderStatus,
  SellerDashboard,
  SellerMove,
  SellerOrder,
  SellerProduct,
  SellerProductFilter,
  SellerProductPatch,
} from "@/types";
import { getToken } from "@/hooks/useAuth";
import { API_URL, http } from "./config";

const auth = () => ({ Authorization: `Bearer ${getToken() ?? ""}` });
const num = (v: unknown) => (v === null || v === undefined ? null : Number(v));

// Backend Decimals arrive as strings; convert once here.
type Raw = Record<string, unknown>;

function fromDashboard(r: Raw): SellerDashboard {
  const d = r as unknown as SellerDashboard;
  const k = r.kpis as Raw;
  const c = r.change as Raw;
  return {
    ...d,
    kpis: { revenue: Number(k.revenue), units_sold: Number(k.units_sold), orders_count: Number(k.orders_count), aov: Number(k.aov) },
    change: {
      revenue_pct: num(c.revenue_pct),
      units_sold_pct: num(c.units_sold_pct),
      orders_count_pct: num(c.orders_count_pct),
      aov_pct: num(c.aov_pct),
    },
    daily: d.daily.map((p) => ({ ...p, revenue: Number(p.revenue) })),
    top_products: d.top_products.map((p) => ({ ...p, revenue: Number(p.revenue) })),
  };
}

function fromOrder(o: SellerOrder): SellerOrder {
  return {
    ...o,
    subtotal_egp: Number(o.subtotal_egp),
    shipping_fee_egp: Number(o.shipping_fee_egp),
    total_egp: Number(o.total_egp),
    items: o.items.map((i) => ({ ...i, line_total_egp: Number(i.line_total_egp) })),
  };
}

export async function getDashboard(days: number): Promise<SellerDashboard> {
  return fromDashboard(await http<Raw>(`/seller/dashboard?days=${days}`, { headers: auth() }));
}

export async function listSellerOrders(status?: OrderStatus): Promise<SellerOrder[]> {
  const q = status ? `?status=${status}&limit=100` : "?limit=100";
  return (await http<SellerOrder[]>(`/seller/orders${q}`, { headers: auth() })).map(fromOrder);
}

export async function advanceOrder(id: number, to_status: SellerMove): Promise<SellerOrder> {
  return fromOrder(
    await http<SellerOrder>(`/seller/orders/${id}/status`, {
      method: "POST",
      headers: auth(),
      body: JSON.stringify({ to_status }),
    }),
  );
}

// ---- products (inventory) ----

function fromProduct(p: SellerProduct): SellerProduct {
  return {
    ...p,
    price_egp: Number(p.price_egp),
    old_price_egp: p.old_price_egp === null ? null : Number(p.old_price_egp),
    rating_avg: p.rating_avg === null ? null : Number(p.rating_avg),
    image_url: p.image_url && p.image_url.startsWith("/") ? `${API_URL}${p.image_url}` : p.image_url,
  };
}

export async function listSellerProducts(filter: SellerProductFilter, q: string): Promise<SellerProduct[]> {
  const params = new URLSearchParams({ filter });
  if (q.trim()) params.set("q", q.trim());
  return (await http<SellerProduct[]>(`/seller/products?${params}`, { headers: auth() })).map(fromProduct);
}

/** Only the fields given are changed. Money is sent as "1234.00" strings (exact decimals). */
export async function updateSellerProduct(id: number, patch: SellerProductPatch): Promise<SellerProduct> {
  const body: Record<string, unknown> = { ...patch };
  if (patch.price_egp !== undefined) body.price_egp = patch.price_egp.toFixed(2);
  if (patch.old_price_egp !== undefined) body.old_price_egp = patch.old_price_egp === null ? null : patch.old_price_egp.toFixed(2);
  return fromProduct(
    await http<SellerProduct>(`/seller/products/${id}`, { method: "PATCH", headers: auth(), body: JSON.stringify(body) }),
  );
}
