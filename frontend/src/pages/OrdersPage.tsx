import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { USE_MOCK } from "@/api/config";
import { useOrders } from "@/hooks/useOrders";
import { useI18n } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { fmtDate, groupPurchases, statusClass, statusKey } from "@/lib/orders";

// One card per purchase (checkout). Each purchase lists its packages (one backend order per seller).
export default function OrdersPage() {
  const { t, lang } = useI18n();
  const { data, isLoading, isError, refetch } = useOrders();
  const Arrow = lang === "ar" ? ChevronLeft : ChevronRight;

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="border-b border-line pb-5 text-3xl">{t("ord.title")}</h1>

      {isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
      {isError && (
        <div className="space-y-2">
          <p className="text-danger">{t("ord.loadErr")}</p>
          <button type="button" className="btn-dark" onClick={() => refetch()}>
            {t("products.retry")}
          </button>
        </div>
      )}
      {data && data.length === 0 && (
        <div className="card space-y-3 p-10 text-center">
          <p className="text-ink-soft">{t("ord.empty")}</p>
          <Link to="/products" className="btn-primary">
            {t("cart.continue")}
          </Link>
        </div>
      )}

      <ul className="space-y-5">
        {data &&
          groupPurchases(data).map((packages) => {
            const first = packages[0];
            const total = packages.reduce((s, o) => s + o.total_egp, 0);
            const items = packages.reduce((s, o) => s + o.items.reduce((n, i) => n + i.qty, 0), 0);
            const many = packages.length > 1;
            return (
              <li key={first.checkout_group_id} className="card space-y-4 p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <p className="font-semibold">{fill(t("ord.placedOn"), { date: fmtDate(first.created_at, lang) })}</p>
                    <p className="text-sm text-ink-soft">{fill(t("ord.items"), { n: items })}</p>
                  </div>
                  <span className="font-display text-xl">{formatPrice(total, lang)}</span>
                </div>
                <ul className="divide-y divide-line rounded-ctl border border-line">
                  {packages.map((o, i) => (
                    <li key={o.id}>
                      <Link to={`/orders/${o.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-sand">
                        <div className="min-w-0 flex-1 space-y-0.5">
                          <p className="text-sm font-medium">
                            {many ? fill(t("co.package"), { i: i + 1, n: packages.length }) : fill(t("oc.order"), { id: o.id })}
                            <span className="ms-2 font-normal text-ink-soft">
                              <bdi>{o.seller_name}</bdi>
                            </span>
                          </p>
                          <p className="truncate text-xs text-ink-soft">
                            <bdi>{o.items.map((it) => it.title).join(lang === "ar" ? "، " : ", ")}</bdi>
                          </p>
                        </div>
                        <span className={`shrink-0 ${statusClass(o.status)}`}>{t(statusKey(o.status))}</span>
                        <Arrow className="h-4 w-4 shrink-0 text-ink-soft" aria-hidden />
                      </Link>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
      </ul>
    </div>
  );
}
