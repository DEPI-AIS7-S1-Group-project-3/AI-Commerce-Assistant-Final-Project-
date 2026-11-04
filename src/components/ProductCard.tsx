import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import type { Product } from "@/types";
import { useCart } from "@/hooks/useCart";
import { useI18n } from "@/lib/i18n";
import { brandName, productTitle, sellerName } from "@/lib/productText";
import { discountPercent, formatPrice, stockState } from "@/lib/format";
import ProductImage from "./ProductImage";

const toneClass = {
  ok: "text-neon",
  low: "text-warn",
  out: "text-danger",
} as const;

export default function ProductCard({ product }: { product: Product }) {
  const { add } = useCart();
  const { t, lang } = useI18n();
  const stock = stockState(product.stock_qty);
  const discount = discountPercent(product.price_egp, product.old_price_egp);
  const soldOut = product.stock_qty <= 0;
  const title = productTitle(product, lang);

  const price = (n: number) => (lang === "ar" ? formatPrice(n) : `EGP ${n.toLocaleString("en-US")}`);
  const stockLabel =
    stock.tone === "out"
      ? t("stock.out" as never)
      : stock.tone === "low"
        ? lang === "ar"
          ? `يتبقى ${product.stock_qty} قطع`
          : `Only ${product.stock_qty} left`
        : t("stock.in");

  return (
    <article className="card flex flex-col overflow-hidden transition-colors hover:border-neon">
      <Link to={`/products/${product.id}`} className="block bg-sand" aria-label={title}>
        <div className="relative aspect-square">
          <ProductImage product={product} className="h-full w-full" />
          {discount && (
            <span className="absolute start-3 top-3 rounded-ctl bg-neon px-2 py-0.5 text-xs font-semibold text-paper">
              {lang === "ar" ? `خصم ${discount}%` : `${discount}% off`}
            </span>
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="space-y-1">
          <p className="text-xs font-medium text-ink-soft">{brandName(product.brand, lang)}</p>
          {/* Body font on purpose: display font is too decorative for long titles mixed with Latin model names. */}
          <h3 className="line-clamp-2 min-h-[3.2rem] font-body text-[15px] font-semibold leading-snug">
            <Link to={`/products/${product.id}`} className="hover:text-neon">
              {title}
            </Link>
          </h3>
        </div>

        <div className="flex items-center gap-2 text-xs text-ink-soft">
          <Star className="h-3.5 w-3.5 fill-neon text-neon" aria-hidden />
          <span className="font-semibold text-ink">{product.rating_avg?.toFixed(1) ?? "-"}</span>
          <span>
            ({product.rating_count} {t("card.reviews")})
          </span>
        </div>

        <div className="mt-auto space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-xl">{price(product.price_egp)}</span>
            {product.old_price_egp && (
              <span className="text-xs text-ink-soft line-through">{price(product.old_price_egp)}</span>
            )}
          </div>
          <p className={`text-xs font-medium ${toneClass[stock.tone]}`}>{stockLabel}</p>
          <p className="text-xs text-ink-soft">
            {t("card.seller")}: {sellerName(product.seller, lang)}
          </p>
        </div>

        <button type="button" className="btn-primary w-full" disabled={soldOut} onClick={() => add(product.id)}>
          {soldOut ? t("card.soldout") : t("card.add")}
        </button>
      </div>
    </article>
  );
}