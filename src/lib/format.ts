// Western digits everywhere, per project rules.
export function formatPrice(value: number): string {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)} ج.م`;
}

export function discountPercent(price: number, oldPrice: number | null): number | null {
  if (!oldPrice || oldPrice <= price) return null;
  return Math.round(((oldPrice - price) / oldPrice) * 100);
}

export type StockState = { tone: "ok" | "low" | "out"; label: string };

export function stockState(qty: number): StockState {
  if (qty <= 0) return { tone: "out", label: "غير متوفر" };
  if (qty <= 5) return { tone: "low", label: `يتبقى ${qty} ${qty === 1 ? "قطعة" : "قطع"}` };
  return { tone: "ok", label: "متوفر في المخزون" };
}
