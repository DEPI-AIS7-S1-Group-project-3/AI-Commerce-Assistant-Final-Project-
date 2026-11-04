import { Link } from "react-router-dom";
import type { Product } from "@/types";
import { useCart } from "@/hooks/useCart";
import { useI18n, type Lang } from "@/lib/i18n";
import { brandName, productTitle, sellerName } from "@/lib/productText";
import { formatPrice } from "@/lib/format";

type Bi = Record<Lang, string>;

const defaultReasons: Bi[] = [
  { ar: "الأعلى تقييمًا من بين المتوفر", en: "Highest rated among what is in stock" },
  { ar: "بديل قوي بتقييم قريب", en: "Strong alternative with a close rating" },
  { ar: "خيار ثالث للمقارنة", en: "A third option to compare" },
];

interface Props {
  products: Product[];
  reasons?: Bi[];
}

export default function RecommendationTable({ products, reasons = defaultReasons }: Props) {
  const { t, lang } = useI18n();
  const { add } = useCart();

  if (!products.length) return null;

  const price = (n: number) => (lang === "ar" ? formatPrice(n) : `EGP ${n.toLocaleString("en-US")}`);

  return (
    <ol className="mt-4 divide-y divide-line border-y border-line">
      {products.map((p, i) => {
        const low = p.stock_qty <= 5;
        const reason = reasons[i]?.[lang] ?? defaultReasons[i % defaultReasons.length][lang];
        return (
          <li key={p.id} className="grid gap-3 py-4 sm:grid-cols-[2rem_1fr_auto] sm:items-center">
            <span className="font-display text-2xl text-neon">{i + 1}</span>
            <div className="space-y-1">
              <Link to={`/products/${p.id}`} className="font-semibold hover:text-neon">
                {productTitle(p, lang)}
              </Link>
              <p className="text-xs text-ink-soft">
                {brandName(p.brand, lang)} · {t("as.sellerlabel")}: {sellerName(p.seller, lang)}
              </p>
              <p className="text-sm text-ink-soft">{reason}</p>
              <p className={`text-xs font-medium ${low ? "text-warn" : "text-neon"}`}>
                {low ? (lang === "ar" ? `يتبقى ${p.stock_qty} قطع` : `Only ${p.stock_qty} left`) : t("stock.in")}
              </p>
            </div>
            <div className="flex items-center gap-3 sm:flex-col sm:items-end">
              <span className="font-display text-xl">{price(p.price_egp)}</span>
              <button type="button" className="btn-primary !px-4 !py-2 text-xs" onClick={() => add(p.id)}>
                {t("card.add")}
              </button>
            </div>
          </li>
        );
      })}
    </ol>
  );
}