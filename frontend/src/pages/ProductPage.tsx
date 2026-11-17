import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { BadgeCheck, Minus, Plus, RotateCcw, ShieldCheck, Star, Truck } from "lucide-react";
import type { Product, ProductReviews } from "@/types";
import { useCart } from "@/hooks/useCart";
import { useProduct, useProducts } from "@/hooks/useProducts";
import { useProductReviews } from "@/hooks/useReviews";
import { useI18n } from "@/lib/i18n";
import { discountPercent, fill, formatPrice, stockState } from "@/lib/format";
import { brandName, productTitle, sellerName } from "@/lib/productText";
import { specRows } from "@/lib/specs";
import ProductCard from "@/components/ProductCard";
import ProductImage from "@/components/ProductImage";

const toneClass = { ok: "text-accent", low: "text-warn", out: "text-danger" } as const;

export default function ProductPage() {
  const { id } = useParams();
  const productId = Number(id);
  const valid = Number.isInteger(productId) && productId > 0;
  const { t } = useI18n();
  const { data: product, isLoading, isError, refetch } = useProduct(valid ? productId : -1);

  if (!valid || (!isLoading && !isError && !product)) {
    return (
      <section className="mx-auto max-w-md space-y-4 py-20 text-center">
        <h1 className="text-3xl">{t("pd.notfound")}</h1>
        <Link to="/products" className="btn-dark">
          {t("pd.back")}
        </Link>
      </section>
    );
  }
  if (isError) {
    return (
      <section className="mx-auto max-w-md space-y-4 py-20 text-center">
        <p>{t("pd.error")}</p>
        <button type="button" className="btn-dark" onClick={() => refetch()}>
          {t("products.retry")}
        </button>
      </section>
    );
  }
  if (isLoading || !product) {
    return <div className="grid animate-pulse gap-8 py-6 lg:grid-cols-2" aria-busy="true"><div className="aspect-square rounded-card bg-sand" /><div className="space-y-4"><div className="h-8 w-3/4 rounded bg-sand" /><div className="h-6 w-1/3 rounded bg-sand" /><div className="h-24 rounded bg-sand" /></div></div>;
  }
  return <ProductView product={product} />;
}

function ProductView({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const { add } = useCart();
  const [imageIdx, setImageIdx] = useState(0);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);

  const title = productTitle(product, lang);
  const price = (n: number) => formatPrice(n, lang);
  const available = product.is_active && product.stock_qty > 0;
  const stock = stockState(product.is_active ? product.stock_qty : 0, t);
  const discount = discountPercent(product.price_egp, product.old_price_egp);
  const maxQty = Math.min(product.stock_qty, 100);
  const image = product.images[imageIdx];
  const specs = specRows(product.specs, product.category.spec_kind, t);

  const addToCart = () => {
    add(product.id, qty);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 2000);
  };

  return (
    <div className="space-y-12">
      <Link to="/products" className="text-sm text-accent hover:underline">
        {t("pd.back")}
      </Link>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* gallery */}
        <div className="space-y-3">
          <div className="aspect-square overflow-hidden rounded-card border-2 border-line bg-sand">
            {image ? (
              <img src={image.url} alt={image.alt_ar ?? title} className="h-full w-full object-contain" />
            ) : (
              <ProductImage product={product} className="h-full w-full" />
            )}
          </div>
          {product.images.length > 1 && (
            <div className="flex gap-2">
              {product.images.map((img, i) => (
                <button
                  key={img.url}
                  type="button"
                  onClick={() => setImageIdx(i)}
                  aria-label={fill(t("pd.image"), { n: i + 1 })}
                  aria-current={i === imageIdx}
                  className={`h-20 w-20 overflow-hidden rounded-ctl border-2 bg-sand ${i === imageIdx ? "border-accent" : "border-line"}`}
                >
                  <img src={img.url} alt="" className="h-full w-full object-contain" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* info */}
        <div className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium text-ink-soft">{brandName(product.brand, lang)}</p>
            <h1 className="font-body text-2xl font-semibold leading-snug">
              <bdi>{title}</bdi>
            </h1>
            <div className="flex items-center gap-2 text-sm text-ink-soft">
              <Star className="h-4 w-4 fill-accent text-accent" aria-hidden />
              <span className="font-semibold text-ink">{product.rating_avg?.toFixed(1) ?? "-"}</span>
              <a href="#reviews" className="hover:text-accent">
                {fill(t("rv.count"), { n: product.rating_count })}
              </a>
            </div>
          </div>

          <div className="flex flex-wrap items-baseline gap-3">
            <span className="font-display text-3xl">{price(product.price_egp)}</span>
            {product.old_price_egp && <span className="text-ink-soft line-through">{price(product.old_price_egp)}</span>}
            {discount && <span className="chip-neon">{fill(t("card.discount"), { n: discount })}</span>}
          </div>

          <p className={`text-sm font-medium ${toneClass[stock.tone]}`}>
            {product.is_active ? stock.label : t("pd.unavailable")}
          </p>

          {available && (
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2" role="group" aria-label={t("pd.qty")}>
                <button type="button" className="btn-ghost !p-2" disabled={qty <= 1} onClick={() => setQty(qty - 1)} aria-label="-">
                  <Minus className="h-4 w-4" aria-hidden />
                </button>
                <span className="min-w-8 text-center font-semibold" dir="ltr">
                  {qty}
                </span>
                <button type="button" className="btn-ghost !p-2" disabled={qty >= maxQty} onClick={() => setQty(qty + 1)} aria-label="+">
                  <Plus className="h-4 w-4" aria-hidden />
                </button>
              </div>
              <button type="button" className="btn-primary flex-1" onClick={addToCart}>
                {t("card.add")}
              </button>
            </div>
          )}
          <p className="min-h-5 text-sm text-accent" aria-live="polite">
            {added ? t("pd.added") : ""}
          </p>

          <p className="text-sm text-ink-soft">
            {t("card.seller")}: <bdi>{sellerName(product.seller, lang)}</bdi>
          </p>

          <ul className="grid gap-2 sm:grid-cols-2">
            <Badge icon={ShieldCheck}>
              {product.warranty_months > 0 ? fill(t("pd.warranty"), { n: product.warranty_months }) : t("pd.warranty.none")}
            </Badge>
            <Badge icon={RotateCcw}>{product.is_returnable ? t("pd.returnable") : t("pd.notReturnable")}</Badge>
            <Badge icon={Truck}>{t("pd.delivery")}</Badge>
            <Badge icon={BadgeCheck}>{t("pd.freeShipping")}</Badge>
          </ul>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-xl">{t("pd.description")}</h2>
          <p dir="auto" className="leading-relaxed text-ink-soft">
            {product.description_ar}
          </p>
        </section>
        {specs.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-xl">{t("pd.specs")}</h2>
            <dl className="divide-y divide-line rounded-card border-2 border-line">
              {specs.map((row) => (
                <div key={row.key} className="flex justify-between gap-4 px-4 py-2.5 text-sm">
                  <dt className="text-ink-soft">{row.label}</dt>
                  <dd className="font-medium" dir="auto">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>

      <ReviewsSection productId={product.id} />
      <SimilarProducts product={product} />
    </div>
  );
}

function Badge({ icon: Icon, children }: { icon: typeof Truck; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2 rounded-ctl border border-line bg-sand px-3 py-2 text-sm">
      <Icon className="h-4 w-4 shrink-0 text-accent" aria-hidden />
      {children}
    </li>
  );
}

function ReviewsSection({ productId }: { productId: number }) {
  const { t, lang } = useI18n();
  const { data } = useProductReviews(productId);
  if (!data) return null;
  return (
    <section id="reviews" className="space-y-4">
      <h2 className="text-xl">{t("rv.title")}</h2>
      {data.total === 0 ? (
        <p className="text-ink-soft">{t("rv.none")}</p>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <Distribution data={data} />
          <ul className="space-y-4">
            {data.reviews.map((r) => (
              <li key={r.id} className="card space-y-2 p-4">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-semibold">{r.author_name}</span>
                  <Stars n={r.rating} />
                  {r.is_verified_purchase && <span className="chip">{t("rv.verified")}</span>}
                  <span className="text-xs text-ink-soft">
                    {new Date(r.created_at).toLocaleDateString(lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB")}
                  </span>
                </div>
                {r.body && (
                  <p dir="auto" className="text-sm leading-relaxed">
                    {r.body}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Distribution({ data }: { data: ProductReviews }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-2">
        <span className="font-display text-4xl">{data.rating_avg?.toFixed(1) ?? "-"}</span>
        <span className="text-sm text-ink-soft">{fill(t("rv.count"), { n: data.rating_count })}</span>
      </div>
      {(["5", "4", "3", "2", "1"] as const).map((k) => {
        const count = data.distribution[k] ?? 0;
        const pct = data.total ? Math.round((count / data.total) * 100) : 0;
        return (
          <div key={k} className="flex items-center gap-2 text-xs" aria-label={fill(t("rv.stars"), { n: k })}>
            <span className="w-3" dir="ltr">{k}</span>
            <Star className="h-3 w-3 fill-accent text-accent" aria-hidden />
            <div className="h-2 flex-1 overflow-hidden rounded bg-sand">
              <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-6 text-end" dir="ltr">{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function Stars({ n }: { n: number }) {
  return (
    <span className="flex" aria-label={`${n}/5`} dir="ltr">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={`h-3.5 w-3.5 ${i <= n ? "fill-accent text-accent" : "text-line"}`} aria-hidden />
      ))}
    </span>
  );
}

function SimilarProducts({ product }: { product: Product }) {
  const { t } = useI18n();
  const { data } = useProducts({ category: product.category.slug });
  const items = (data ?? []).filter((p) => p.id !== product.id).slice(0, 4);
  if (items.length === 0) return null;
  return (
    <section className="space-y-4">
      <h2 className="text-xl">{t("pd.similar")}</h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </section>
  );
}
