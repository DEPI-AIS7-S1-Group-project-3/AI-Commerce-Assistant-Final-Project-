import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Laptop, Smartphone, Headphones, type LucideIcon } from "lucide-react";
import { useProducts } from "@/hooks/useProducts";
import { useI18n, type TKey } from "@/lib/i18n";
import ProductCard from "@/components/ProductCard";
import ProductCardSkeleton from "@/components/ProductCardSkeleton";

const categoryTiles: { slug: string; label: TKey; hint: TKey; Icon: LucideIcon }[] = [
  { slug: "mobiles", label: "cat.mobiles", hint: "cat.mobiles.d", Icon: Smartphone },
  { slug: "laptops", label: "cat.laptops", hint: "cat.laptops.d", Icon: Laptop },
  { slug: "audio", label: "cat.audio", hint: "cat.audio.d", Icon: Headphones },
];

const stats: { value: TKey; label: TKey }[] = [
  { value: "home.delivery.v", label: "home.delivery.l" },
  { value: "home.return.v", label: "home.return.l" },
  { value: "home.ship.v", label: "home.ship.l" },
];

export default function HomePage() {
  const { t, lang } = useI18n();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;
  const { data, isLoading } = useProducts({ sort: "rating", in_stock: true });
  const featured = data?.slice(0, 4) ?? [];

  return (
    <div className="space-y-16">
      <section className="grid items-end gap-8 border-b border-line pb-12 md:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <p className="text-sm font-semibold text-neon">{t("tagline")}</p>
          <h1 className="text-4xl leading-tight sm:text-6xl">
            {t("home.title1")}
            <br />
            {t("home.title2")}
          </h1>
          <p className="max-w-xl text-lg text-ink-soft">{t("home.sub")}</p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link to="/products" className="btn-primary !px-6 !py-3">
              {t("home.browse")}
            </Link>
            <Link to="/products?sort=price_asc" className="btn-ghost !px-6 !py-3">
              {t("home.cheapest")}
            </Link>
          </div>
        </div>

        <dl className="grid grid-cols-3 gap-4 text-center md:grid-cols-1 md:text-start">
          {stats.map(({ value, label }) => (
            <div key={label} className="border-t border-line pt-3">
              <dt className="font-display text-2xl">{t(value)}</dt>
              <dd className="text-sm text-ink-soft">{t(label)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="cats" className="space-y-5">
        <h2 id="cats" className="text-2xl">
          {t("home.categories")}
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {categoryTiles.map(({ slug, label, hint, Icon }) => (
            <Link
              key={slug}
              to={`/products?category=${slug}`}
              className="card group flex items-start justify-between gap-4 p-6 transition-colors hover:border-neon"
            >
              <div className="space-y-1">
                <h3 className="text-xl">{t(label)}</h3>
                <p className="text-sm text-ink-soft">{t(hint)}</p>
              </div>
              <Icon className="h-7 w-7 shrink-0 text-neon" aria-hidden />
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="top" className="space-y-5">
        <div className="flex items-end justify-between">
          <h2 id="top" className="text-2xl">
            {t("home.top")}
          </h2>
          <Link to="/products?sort=rating" className="inline-flex items-center gap-1 text-sm font-semibold text-neon hover:text-neon-deep">
            {t("home.viewall")}
            <Arrow className="h-4 w-4" aria-hidden />
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {isLoading
            ? Array.from({ length: 4 }, (_, i) => <ProductCardSkeleton key={i} />)
            : featured.map((p) => <ProductCard key={p.id} product={p} />)}
        </div>
      </section>
    </div>
  );
}