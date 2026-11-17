import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight, PackageCheck } from "lucide-react";
import type { OrderStatus } from "@/types";
import { USE_MOCK } from "@/api/config";
import { useSellerDashboard } from "@/hooks/useSeller";
import { useI18n } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { statusClass, statusKey } from "@/lib/orders";
import SalesChart from "@/components/seller/SalesChart";

const PERIODS = [7, 30, 90] as const;
const STATUS_ORDER: OrderStatus[] = ["pending", "confirmed", "shipped", "out_for_delivery", "delivered", "return_requested", "returned", "cancelled"];

export default function SellerDashboardPage() {
  const { t, lang } = useI18n();
  const [days, setDays] = useState<number>(30);
  const { data, isLoading, isError, refetch } = useSellerDashboard(days);
  const price = (n: number) => formatPrice(n, lang);

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;
  if (isError)
    return (
      <div className="space-y-2">
        <p className="text-danger">{t("sel.loadErr")}</p>
        <button type="button" className="btn-dark" onClick={() => refetch()}>
          {t("products.retry")}
        </button>
      </div>
    );
  if (isLoading || !data) return <p className="text-ink-soft">{t("cart.loading")}...</p>;

  const kpis: { label: string; value: string; pct: number | null }[] = [
    { label: t("sel.revenue"), value: price(data.kpis.revenue), pct: data.change.revenue_pct },
    { label: t("sel.orders"), value: String(data.kpis.orders_count), pct: data.change.orders_count_pct },
    { label: t("sel.units"), value: String(data.kpis.units_sold), pct: data.change.units_sold_pct },
    { label: t("sel.aov"), value: price(data.kpis.aov), pct: data.change.aov_pct },
  ];

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div className="space-y-1">
          <p className="text-sm text-ink-soft">{t("sel.title")}</p>
          <h1 className="text-3xl">
            <bdi>{data.store_name}</bdi>
          </h1>
        </div>
        <div className="flex gap-1 rounded-ctl border border-line p-1" role="group" aria-label={t("sel.period")}>
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setDays(p)}
              aria-pressed={p === days}
              className={`rounded-ctl px-3 py-1.5 text-sm ${p === days ? "bg-neon font-semibold text-on-neon" : "text-ink-soft hover:text-ink"}`}
            >
              {fill(t("sel.days"), { n: p })}
            </button>
          ))}
        </div>
      </header>

      {data.pending_actions > 0 && (
        <Link to="/seller/orders" className="card flex items-center gap-3 p-4 hover:border-accent">
          <PackageCheck className="h-5 w-5 text-accent" aria-hidden />
          <span className="font-medium">{fill(t("sel.pending"), { n: data.pending_actions })}</span>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="card space-y-1 p-4">
            <p className="text-xs text-ink-soft">{k.label}</p>
            <p className="font-display text-2xl">{k.value}</p>
            <Change pct={k.pct} />
          </div>
        ))}
      </div>
      <p className="-mt-5 text-xs text-ink-soft">{fill(t("sel.vsPrev"), { n: days })}</p>

      <section className="card space-y-3 p-5">
        <h2 className="text-lg">{t("sel.daily")}</h2>
        <SalesChart data={data.daily} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-3 p-5">
          <h2 className="text-lg">{t("sel.top")}</h2>
          {data.top_products.length === 0 ? (
            <p className="text-sm text-ink-soft">{t("sel.noSales")}</p>
          ) : (
            <ol className="divide-y divide-line text-sm">
              {data.top_products.map((p, i) => (
                <li key={p.product_id} className="flex items-center gap-3 py-2">
                  <span className="w-5 text-ink-soft" dir="ltr">{i + 1}</span>
                  <Link to={`/products/${p.product_id}`} className="min-w-0 flex-1 truncate hover:text-accent">
                    <bdi>{p.title}</bdi>
                  </Link>
                  <span className="shrink-0 text-ink-soft">{fill(t("sel.unitsN"), { n: p.units_sold })}</span>
                  <span className="shrink-0 font-medium">{price(p.revenue)}</span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="card space-y-3 p-5">
          <h2 className="text-lg">{t("sel.lowStock")}</h2>
          {data.low_stock.length === 0 ? (
            <p className="text-sm text-ink-soft">{t("sel.stockOk")}</p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {data.low_stock.map((p) => (
                <li key={p.product_id} className="flex items-center gap-3 py-2">
                  <Link to={`/products/${p.product_id}`} className="min-w-0 flex-1 truncate hover:text-accent">
                    <bdi>{p.title}</bdi>
                  </Link>
                  <span className={`shrink-0 font-semibold ${p.stock_qty === 0 ? "text-danger" : "text-warn"}`}>
                    {p.stock_qty === 0 ? t("stock.out") : fill(t("sel.left"), { n: p.stock_qty })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg">{t("sel.byStatus")}</h2>
        <div className="flex flex-wrap gap-2">
          {STATUS_ORDER.filter((s) => data.orders_by_status[s]).map((s) => (
            <Link key={s} to={`/seller/orders?status=${s}`} className={`${statusClass(s)} !px-3 !py-1.5 !text-sm`}>
              {t(statusKey(s))}: {data.orders_by_status[s]}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function Change({ pct }: { pct: number | null }) {
  const { t } = useI18n();
  if (pct === null) return <p className="text-xs text-ink-soft">{t("sel.noPrev")}</p>;
  const up = pct >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <p className={`flex items-center gap-1 text-xs font-medium ${up ? "text-accent" : "text-danger"}`} dir="ltr">
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {up ? "+" : ""}
      {pct}%
    </p>
  );
}
