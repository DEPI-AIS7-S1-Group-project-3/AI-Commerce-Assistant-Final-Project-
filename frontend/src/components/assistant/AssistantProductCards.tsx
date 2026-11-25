import { Link } from "react-router-dom";
import { useI18n } from "@/lib/i18n";
import { formatPrice } from "@/lib/format";
import { useCart } from "@/hooks/useCart";
import type { ProductCard } from "@/api/assistant";
import ProductImage from "@/components/ProductImage";

interface Props {
  products: ProductCard[];
}

/**
 * Product cards that come from the assistant /chat response.
 * Lighter than the full <ProductCard> component because the backend only returns a subset of fields.
 */
export default function AssistantProductCards({ products }: Props) {
  const { lang, t } = useI18n();
  const { add } = useCart();

  if (!products.length) return null;

  return (
    <ol className="mt-4 divide-y divide-line border-y border-line">
      {products.map((p) => {
        const price = Number(p.price_egp);
        const oldPrice = p.old_price_egp ? Number(p.old_price_egp) : null;
        const rating = p.rating_avg ? Number(p.rating_avg) : null;

        return (
          <li key={p.id} className="grid gap-3 py-4 sm:grid-cols-[3rem_1fr_auto] sm:items-center">
            {/* Thumbnail – category icon or image fallback */}
            <div className="hidden sm:block">
              <ProductImage categorySlug={p.category_slug} title={p.title_ar} className="h-12 w-12 rounded object-contain" />
            </div>

            <div className="space-y-1">
              <Link to={`/products/${p.id}`} className="font-semibold hover:text-accent">
                <bdi>{p.title_ar}</bdi>
              </Link>
              <p className="text-xs text-ink-soft">
                {p.brand} · {p.category_slug}
              </p>
              {rating !== null && (
                <p className="text-xs text-ink-soft">
                  ★ {rating.toFixed(1)} ({p.rating_count})
                </p>
              )}
              <p className={`text-xs font-medium ${p.in_stock ? "text-accent" : "text-danger"}`}>
                {p.in_stock ? t("stock.in") : t("stock.out")}
              </p>
            </div>

            <div className="flex items-center gap-3 sm:flex-col sm:items-end">
              <div className="text-end">
                <span className="font-display text-xl">{formatPrice(price, lang)}</span>
                {oldPrice && oldPrice > price && (
                  <span className="ms-2 text-sm text-ink-soft line-through">
                    {formatPrice(oldPrice, lang)}
                  </span>
                )}
              </div>
              {p.in_stock && (
                <button
                  type="button"
                  className="btn-primary !px-4 !py-2 text-xs"
                  onClick={() => add(p.id)}
                >
                  {t("card.add")}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
