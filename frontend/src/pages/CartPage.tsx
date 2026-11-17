import { Link } from "react-router-dom";
import { Minus, Plus, Trash2 } from "lucide-react";
import type { Product } from "@/types";
import { useAuth } from "@/hooks/useAuth";
import { useCart } from "@/hooks/useCart";
import { useQueries } from "@tanstack/react-query";
import { getProduct } from "@/api/products";
import { useI18n } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { productTitle, sellerName } from "@/lib/productText";
import ProductImage from "@/components/ProductImage";
import { FREE_FROM, SHIPPING_FEE } from "@/lib/shipping";


export default function CartPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const { lines, setQty, remove, clear, error } = useCart();
  // Load each cart product by id (not the listing): the listing hides inactive products
  // and is paged, but the cart must still show items that became unavailable.
  const results = useQueries({
    queries: lines.map((l) => ({ queryKey: ["product", l.product_id], queryFn: () => getProduct(l.product_id) })),
  });
  const isLoading = results.some((r) => r.isLoading);

  const price = (n: number) => formatPrice(n, lang);

  if (lines.length === 0) {
    return (
      <div className="card mx-auto max-w-xl space-y-3 p-10 text-center">
        <h1 className="text-3xl">{t("cart.empty")}</h1>
        <p className="text-ink-soft">{t("cart.empty.hint")}</p>
        <Link to="/products" className="btn-primary">
          {t("cart.continue")}
        </Link>
      </div>
    );
  }

  if (isLoading) return <p className="text-ink-soft">{t("cart.loading")}...</p>;

  const rows = lines.map((line, i) => ({ line, product: results[i]?.data ?? undefined }));
  const isAvailable = (p?: Product): p is Product => Boolean(p && p.is_active && p.stock_qty > 0);

  // Quantity is capped by stock; unavailable lines are excluded from every total.
  const available = rows
    .filter((r) => isAvailable(r.product))
    .map((r) => {
      const p = r.product as Product;
      const qty = Math.min(r.line.qty, p.stock_qty);
      return { product: p, qty, lineTotal: p.price_egp * qty };
    });

  const bySeller = new Map<number, { name: string; subtotal: number }>();
  available.forEach(({ product, lineTotal }) => {
    const cur = bySeller.get(product.seller.id) ?? { name: sellerName(product.seller, lang), subtotal: 0 };
    cur.subtotal += lineTotal;
    bySeller.set(product.seller.id, cur);
  });

  const groups = [...bySeller.entries()].map(([id, g]) => ({
    id,
    ...g,
    fee: g.subtotal >= FREE_FROM ? 0 : SHIPPING_FEE,
    missing: Math.max(0, FREE_FROM - g.subtotal),
  }));
  const subtotal = groups.reduce((s, g) => s + g.subtotal, 0);
  const shipping = groups.reduce((s, g) => s + g.fee, 0);
  const total = subtotal + shipping;

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 border-b border-line pb-5">
        <h1 className="text-3xl">{t("cart.title")}</h1>
        <button type="button" className="text-sm text-ink-soft hover:text-danger" onClick={clear}>
          {t("cart.clear")}
        </button>
      </header>

      {error && (
        <p className="rounded-ctl border border-danger px-4 py-3 text-sm text-danger" role="alert">
          {t(`cart.err.${error}`)}
        </p>
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
        <ul className="space-y-4">
          {rows.map(({ line, product }) => {
            if (!product) {
              return (
                <li key={line.product_id} className="card flex items-center justify-between gap-4 p-4 opacity-70">
                  <p className="text-sm">{t("cart.removed")}</p>
                  <button type="button" className="btn-ghost !px-3 !py-2 text-xs" onClick={() => remove(line.product_id)}>
                    {t("cart.remove")}
                  </button>
                </li>
              );
            }
            const ok = isAvailable(product);
            const qty = Math.min(line.qty, Math.max(product.stock_qty, 1));
            const atMax = ok && qty >= product.stock_qty;
            return (
              <li key={product.id} className={`card flex gap-4 p-4 ${ok ? "" : "opacity-70"}`}>
                <Link to={`/products/${product.id}`} className="block h-24 w-24 shrink-0 overflow-hidden rounded-ctl bg-sand">
                  <ProductImage product={product} className="h-full w-full" />
                </Link>
                <div className="flex flex-1 flex-col gap-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <Link to={`/products/${product.id}`} className="font-semibold hover:text-accent">
                        <bdi>{productTitle(product, lang)}</bdi>
                      </Link>
                      <p className="text-xs text-ink-soft"><bdi>{sellerName(product.seller, lang)}</bdi></p>
                    </div>
                    <span className="font-display text-lg">{price(product.price_egp)}</span>
                  </div>

                  {!ok && <p className="text-xs text-danger">{t("cart.unavailable")}</p>}

                  <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
                    {ok ? (
                      <div className="flex items-center gap-2" role="group" aria-label={t("cart.qty")}>
                        <button type="button" className="btn-ghost !p-2" disabled={qty <= 1} onClick={() => setQty(product.id, qty - 1)} aria-label="-">
                          <Minus className="h-4 w-4" aria-hidden />
                        </button>
                        <span className="min-w-8 text-center font-semibold" dir="ltr">
                          {qty}
                        </span>
                        <button type="button" className="btn-ghost !p-2" disabled={atMax} onClick={() => setQty(product.id, qty + 1)} aria-label="+">
                          <Plus className="h-4 w-4" aria-hidden />
                        </button>
                        {atMax && <span className="text-xs text-warn">{t("cart.maxstock")}</span>}
                      </div>
                    ) : (
                      <span />
                    )}
                    <button type="button" className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-danger" onClick={() => remove(product.id)}>
                      <Trash2 className="h-4 w-4" aria-hidden />
                      {t("cart.remove")}
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        <aside className="card h-fit space-y-4 p-5" aria-label={t("cart.summary")}>
          <h2 className="text-xl">{t("cart.summary")}</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-soft">{t("cart.subtotal")}</dt>
              <dd>{price(subtotal)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-soft">{t("cart.shipping")}</dt>
              <dd className={shipping === 0 ? "text-accent" : ""}>{shipping === 0 ? t("cart.shipping.free") : price(shipping)}</dd>
            </div>
            {/* Shipping is charged per seller; only explain it when a seller is under the free threshold. */}
            {groups
              .filter((g) => g.fee > 0 && g.missing > 0)
              .map((g) => (
                <p key={g.id} className="text-xs text-ink-soft">
                  {fill(t("cart.freeHint"), { amount: price(g.missing), seller: `\u2068${g.name}\u2069` })}
                </p>
              ))}
            <div className="flex justify-between border-t border-line pt-3 text-base font-semibold">
              <dt>{t("cart.total")}</dt>
              <dd className="font-display text-xl">{price(total)}</dd>
            </div>
          </dl>

          {available.length === 0 ? (
            <button type="button" className="btn-primary w-full" disabled>
              {t("cart.checkout")}
            </button>
          ) : user ? (
            <Link to="/checkout" className="btn-primary w-full">
              {t("cart.checkout")}
            </Link>
          ) : (
            <Link to="/login" state={{ from: "/cart" }} className="btn-primary w-full">
              {t("cart.checkout.login")}
            </Link>
          )}
        </aside>
      </div>
    </div>
  );
}