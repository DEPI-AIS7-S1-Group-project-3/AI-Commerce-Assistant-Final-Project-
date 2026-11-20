import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Package, Search } from "lucide-react";
import type { SellerProduct, SellerProductFilter } from "@/types";
import { ApiError, USE_MOCK } from "@/api/config";
import { useSellerProducts, useUpdateSellerProduct } from "@/hooks/useSeller";
import { useI18n, type TKey } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";

const FILTERS: { id: SellerProductFilter; label: TKey }[] = [
  { id: "all", label: "filter.all" },
  { id: "visible", label: "sp.f.visible" },
  { id: "hidden", label: "sp.f.hidden" },
  { id: "low", label: "sp.f.low" },
  { id: "out", label: "sp.f.out" },
];

// Seller inventory: price, old price, stock and visibility. Products are never deleted
// (orders and reviews point to them): "hide" takes them off the shop.
export default function SellerProductsPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const filter = (params.get("filter") ?? "all") as SellerProductFilter;
  const [term, setTerm] = useState(params.get("q") ?? "");
  const q = params.get("q") ?? "";
  const { data, isLoading, isError, refetch } = useSellerProducts(filter, q);

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;

  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v && v !== "all") next.set(k, v);
    else next.delete(k);
    setParams(next);
  };
  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    setParam("q", term.trim());
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
        <h1 className="text-3xl">{t("sp.title")}</h1>
        <Link to="/seller" className="text-sm text-accent hover:underline">
          {t("sel.backToDashboard")}
        </Link>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={onSearch} role="search" className="relative min-w-0 flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" aria-hidden />
          <input className="input ps-9" value={term} onChange={(e) => setTerm(e.target.value)} placeholder={t("sp.search")} aria-label={t("sp.search")} />
        </form>
        <nav className="flex gap-2 overflow-x-auto" aria-label={t("sel.filter")}>
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setParam("filter", f.id)}
              aria-pressed={f.id === filter}
              className={`shrink-0 rounded-ctl px-3 py-1.5 text-sm ${f.id === filter ? "bg-neon font-semibold text-on-neon" : "border border-line text-ink-soft hover:text-ink"}`}
            >
              {t(f.label)}
            </button>
          ))}
        </nav>
      </div>

      {isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
      {isError && (
        <button type="button" className="btn-dark" onClick={() => refetch()}>
          {t("products.retry")}
        </button>
      )}
      {data && data.length === 0 && <p className="text-ink-soft">{t("sp.empty")}</p>}

      <ul className="space-y-3">
        {data?.map((p) => (
          <ProductRow key={p.id} p={p} />
        ))}
      </ul>
    </div>
  );
}

function ProductRow({ p }: { p: SellerProduct }) {
  const { t, lang } = useI18n();
  const update = useUpdateSellerProduct();
  const [editing, setEditing] = useState(false);
  // Form uses "regular price" + optional "sale price"; stored as price_egp (what the customer
  // pays) + old_price_egp (crossed-out regular price) when there is a sale.
  const initRegular = () => String(p.old_price_egp ?? p.price_egp);
  const initSale = () => (p.old_price_egp === null ? "" : String(p.price_egp));
  const [regular, setRegular] = useState(initRegular);
  const [sale, setSale] = useState(initSale);
  const [stock, setStock] = useState(String(p.stock_qty));
  const [invalid, setInvalid] = useState<TKey | null>(null);
  const title = lang === "en" && p.title_en ? p.title_en : p.title_ar;

  const reset = () => {
    setRegular(initRegular());
    setSale(initSale());
    setStock(String(p.stock_qty));
    setInvalid(null);
    update.reset();
  };

  const save = () => {
    const reg = Number(regular);
    const sl = sale.trim() === "" ? null : Number(sale);
    const st = Number(stock);
    if (!(reg > 0) || !Number.isFinite(reg)) return setInvalid("sp.v.price");
    if (sl !== null && (!(sl > 0) || !Number.isFinite(sl) || sl >= reg)) return setInvalid("sp.v.sale");
    if (!Number.isInteger(st) || st < 0) return setInvalid("sp.v.stock");
    setInvalid(null);
    const patch = sl === null ? { price_egp: reg, old_price_egp: null } : { price_egp: sl, old_price_egp: reg };
    update.mutate(
      { id: p.id, patch: { ...patch, stock_qty: st } },
      { onSuccess: () => setEditing(false) },
    );
  };

  const serverErr: TKey | null = update.error
    ? update.error instanceof ApiError && update.error.code === "invalid_old_price"
      ? "sp.v.sale"
      : update.error instanceof ApiError && update.error.status === 422
        ? "sp.v.generic"
        : "ord.err.generic"
    : null;
  const stockClass = p.stock_qty === 0 ? "text-danger" : p.stock_qty <= 5 ? "text-warn" : "text-ink-soft";

  return (
    <li className={`card space-y-3 p-4 ${p.is_active ? "" : "opacity-70"}`}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="h-14 w-14 shrink-0 overflow-hidden rounded-ctl bg-sand">
          {p.image_url ? (
            <img src={p.image_url} alt="" className="h-full w-full object-contain" />
          ) : (
            <Package className="m-4 h-6 w-6 text-ink-soft" aria-hidden />
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-0.5">
          <Link to={`/products/${p.id}`} className="block truncate font-semibold hover:text-accent">
            <bdi>{title}</bdi>
          </Link>
          <p className="text-xs text-ink-soft" dir="ltr">
            {p.sku} · {p.brand}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3 text-sm">
          <span className="font-semibold">{formatPrice(p.price_egp, lang)}</span>
          {p.old_price_egp !== null && <span className="text-xs text-ink-soft line-through">{formatPrice(p.old_price_egp, lang)}</span>}
          <span className={`font-medium ${stockClass}`}>
            {p.stock_qty === 0 ? t("stock.out") : fill(t("sp.stockN"), { n: p.stock_qty })}
          </span>
          <span className={p.is_active ? "chip-neon" : "chip"}>{p.is_active ? t("sp.visible") : t("sp.hidden")}</span>
        </div>
      </div>

      {editing ? (
        <div className="space-y-3 rounded-ctl border border-line bg-sand p-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block space-y-1 text-sm">
              <span>{t("sp.regular")}</span>
              <input className="input" dir="ltr" inputMode="decimal" value={regular} onChange={(e) => setRegular(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>{t("sp.sale")}</span>
              <input className="input" dir="ltr" inputMode="decimal" placeholder={t("sp.sale.hint")} value={sale} onChange={(e) => setSale(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>{t("sp.stock")}</span>
              <input className="input" dir="ltr" inputMode="numeric" value={stock} onChange={(e) => setStock(e.target.value.replace(/\D/g, ""))} />
            </label>
          </div>
          {(invalid || serverErr) && (
            <p className="text-sm text-danger" role="alert">
              {t(invalid ?? serverErr!)}
            </p>
          )}
          <div className="flex gap-2">
            <button type="button" className="btn-primary !py-2" disabled={update.isPending} onClick={save}>
              {t("addr.save")}
            </button>
            <button
              type="button"
              className="btn-ghost !py-2"
              onClick={() => {
                reset();
                setEditing(false);
              }}
            >
              {t("addr.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-ghost !px-3 !py-2 text-xs"
            onClick={() => {
              reset();
              setEditing(true);
            }}
          >
            {t("sp.edit")}
          </button>
          <button
            type="button"
            className="btn-ghost !px-3 !py-2 text-xs"
            disabled={update.isPending}
            onClick={() => update.mutate({ id: p.id, patch: { is_active: !p.is_active } })}
          >
            {p.is_active ? t("sp.hide") : t("sp.show")}
          </button>
        </div>
      )}
    </li>
  );
}
