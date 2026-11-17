import type { Lang, TKey } from "@/lib/i18n";

type T = (k: TKey) => string;

/** Fill {name} placeholders in a dictionary string: fill("Only {n} left", { n: 3 }). */
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

// Western digits everywhere, per project rules. AR: "23,499 ج.م"  EN: "EGP 23,499"
export function formatPrice(value: number, lang: Lang): string {
  const n = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  return lang === "ar" ? `${n} ج.م` : `EGP ${n}`;
}

export function discountPercent(price: number, oldPrice: number | null): number | null {
  if (!oldPrice || oldPrice <= price) return null;
  return Math.round(((oldPrice - price) / oldPrice) * 100);
}

export type StockState = { tone: "ok" | "low" | "out"; label: string };

export function stockState(qty: number, t: T): StockState {
  if (qty <= 0) return { tone: "out", label: t("stock.out") };
  if (qty <= 5) {
    return { tone: "low", label: fill(t(qty === 1 ? "stock.left.one" : "stock.left.many"), { n: qty }) };
  }
  return { tone: "ok", label: t("stock.in") };
}
