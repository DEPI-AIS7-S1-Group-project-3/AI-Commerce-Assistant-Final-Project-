import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SlidersHorizontal, X } from "lucide-react";
import { useBrands, useCategories, useProducts } from "@/hooks/useProducts";
import { useI18n, type TKey } from "@/lib/i18n";
import { categoryName } from "@/lib/productText";
import type { ProductQuery, ProductSort } from "@/types";
import FilterPanel, { type FilterValues } from "@/components/FilterPanel";
import ProductCard from "@/components/ProductCard";
import ProductCardSkeleton from "@/components/ProductCardSkeleton";

const sortOptions: { value: ProductSort; label: TKey }[] = [
  { value: "newest", label: "sort.newest" },
  { value: "price_asc", label: "sort.price_asc" },
  { value: "price_desc", label: "sort.price_desc" },
  { value: "rating", label: "sort.rating" },
];

const isSort = (v: string | null): v is ProductSort => sortOptions.some((o) => o.value === v);

export default function ProductsPage() {
  const { t, lang } = useI18n();
  // The URL is the single source of truth for filters (shareable links, back button works).
  const [params, setParams] = useSearchParams();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const sortParam = params.get("sort");
  const values: FilterValues = {
    category: params.get("category") ?? "",
    brand: params.get("brand") ?? "",
    min_price: params.get("min_price") ?? "",
    max_price: params.get("max_price") ?? "",
    in_stock: params.get("in_stock") === "1",
  };
  const q = params.get("q") ?? "";
  const sort: ProductSort = isSort(sortParam) ? sortParam : "newest";

  const query: ProductQuery = {
    q: q || undefined,
    category: values.category || undefined,
    brand: values.brand || undefined,
    min_price: values.min_price ? Number(values.min_price) : undefined,
    max_price: values.max_price ? Number(values.max_price) : undefined,
    in_stock: values.in_stock || undefined,
    sort,
  };

  const { data: products, isLoading, isError, refetch } = useProducts(query);
  const { data: categories = [] } = useCategories();
  const { data: brands = [] } = useBrands();

  const update = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };

  const onFilterChange = (patch: Partial<FilterValues>) => {
    const mapped: Record<string, string | undefined> = {};
    if ("category" in patch) mapped.category = patch.category;
    if ("brand" in patch) mapped.brand = patch.brand;
    if ("min_price" in patch) mapped.min_price = patch.min_price;
    if ("max_price" in patch) mapped.max_price = patch.max_price;
    if ("in_stock" in patch) mapped.in_stock = patch.in_stock ? "1" : undefined;
    update(mapped);
  };

  const reset = () => setParams(q ? { q } : {}, { replace: true });

  const panel = (
    <FilterPanel values={values} categories={categories} brands={brands} onChange={onFilterChange} onReset={reset} />
  );

  const activeCat = categories.find((c) => c.slug === values.category);
  const count = products?.length ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div className="space-y-1">
          <h1 className="text-3xl">
            {q ? `${t("products.search")} ${q}` : activeCat ? categoryName(activeCat, lang) : t("products.all")}
          </h1>
          <p className="text-sm text-ink-soft" aria-live="polite">
            {isLoading ? t("products.loading") : lang === "ar" ? `${count} منتج` : `${count} products`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button type="button" className="btn-ghost lg:hidden" onClick={() => setDrawerOpen(true)}>
            <SlidersHorizontal className="h-4 w-4" aria-hidden />
            {t("products.filters")}
          </button>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-ink-soft">{t("products.sort")}</span>
            <select className="input !w-auto" value={sort} onChange={(e) => update({ sort: e.target.value })}>
              {sortOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {t(o.label)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <aside className="hidden lg:block" aria-label={t("products.filters")}>
          {panel}
        </aside>

        <section aria-label={t("products.list")}>
          {isError ? (
            <div className="card space-y-3 p-8 text-center">
              <p className="font-semibold">{t("products.error")}</p>
              <button type="button" className="btn-dark" onClick={() => refetch()}>
                {t("products.retry")}
              </button>
            </div>
          ) : isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <ProductCardSkeleton key={i} />
              ))}
            </div>
          ) : products && products.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {products.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          ) : (
            <div className="card space-y-3 p-10 text-center">
              <h2 className="text-xl">{t("products.empty.title")}</h2>
              <p className="text-sm text-ink-soft">{t("products.empty.hint")}</p>
              <button type="button" className="btn-ghost" onClick={reset}>
                {t("products.clear")}
              </button>
            </div>
          )}
        </section>
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t("products.filters")}>
          <button type="button" className="absolute inset-0 bg-black/60" aria-label={t("products.close")} onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 end-0 w-80 max-w-[90vw] overflow-y-auto bg-paper p-5">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl">{t("products.filters")}</h2>
              <button type="button" className="btn-ghost !p-2" onClick={() => setDrawerOpen(false)} aria-label={t("products.close")}>
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
            {panel}
            <button type="button" className="btn-primary mt-6 w-full" onClick={() => setDrawerOpen(false)}>
              {t("products.show")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}