import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { OrderStatus, SellerMove } from "@/types";
import { ApiError, USE_MOCK } from "@/api/config";
import { useAdvanceOrder, useSellerOrders } from "@/hooks/useSeller";
import { useI18n, type TKey } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { fmtDate, statusClass, statusKey } from "@/lib/orders";
import { governorateName } from "@/lib/governorates";

const FILTERS: (OrderStatus | "")[] = ["", "pending", "confirmed", "shipped", "out_for_delivery", "delivered", "return_requested", "cancelled"];
const MOVE_LABEL: Record<SellerMove, TKey> = {
  confirmed: "sel.move.confirmed",
  shipped: "sel.move.shipped",
  out_for_delivery: "sel.move.out_for_delivery",
  delivered: "sel.move.delivered",
};

export default function SellerOrdersPage() {
  const { t, lang } = useI18n();
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") ?? "") as OrderStatus | "";
  const { data, isLoading, isError, refetch } = useSellerOrders(status || undefined);
  const advance = useAdvanceOrder();
  const [confirming, setConfirming] = useState<number | null>(null);
  const price = (n: number) => formatPrice(n, lang);

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;

  const errKey: TKey | null = advance.error
    ? advance.error instanceof ApiError && advance.error.code === "invalid_transition"
      ? "sel.err.transition"
      : "ord.err.generic"
    : null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
        <h1 className="text-3xl">{t("sel.ordersTitle")}</h1>
        <Link to="/seller" className="text-sm text-accent hover:underline">
          {t("sel.backToDashboard")}
        </Link>
      </header>

      <nav className="flex gap-2 overflow-x-auto pb-1" aria-label={t("sel.filter")}>
        {FILTERS.map((s) => (
          <button
            key={s || "all"}
            type="button"
            onClick={() => setParams(s ? { status: s } : {})}
            aria-pressed={s === status}
            className={`shrink-0 rounded-ctl px-3 py-1.5 text-sm ${s === status ? "bg-neon font-semibold text-on-neon" : "border border-line text-ink-soft hover:text-ink"}`}
          >
            {s ? t(statusKey(s)) : t("filter.all")}
          </button>
        ))}
      </nav>

      {errKey && (
        <p className="text-sm text-danger" role="alert">
          {t(errKey)}
        </p>
      )}
      {isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
      {isError && (
        <button type="button" className="btn-dark" onClick={() => refetch()}>
          {t("products.retry")}
        </button>
      )}
      {data && data.length === 0 && <p className="text-ink-soft">{t("sel.noOrders")}</p>}

      <ul className="space-y-4">
        {data?.map((o) => (
          <li key={o.id} className="card space-y-3 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="space-y-0.5">
                <p className="font-semibold" dir="auto">
                  {fill(t("oc.order"), { id: o.id })}
                </p>
                <p className="text-xs text-ink-soft">
                  {fmtDate(o.created_at, lang)} · <bdi>{o.customer_name}</bdi>
                  {o.governorate && (
                    <>
                      {" · "}
                      <bdi>{[o.city, governorateName(o.governorate, lang)].filter(Boolean).join(lang === "ar" ? "، " : ", ")}</bdi>
                    </>
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={o.payment_status === "paid" ? "chip-neon" : "chip"}>
                  {o.payment_status === "paid" ? t("oc.paid") : t("oc.pending")}
                </span>
                <span className={statusClass(o.status)}>{t(statusKey(o.status))}</span>
              </div>
            </div>

            <ul className="space-y-1 text-sm">
              {o.items.map((i) => (
                <li key={i.product_id} className="flex justify-between gap-3">
                  <span className="min-w-0">
                    <bdi>{i.title}</bdi> <span className="text-ink-soft" dir="ltr">× {i.qty}</span>
                  </span>
                  <span className="shrink-0">{price(i.line_total_egp)}</span>
                </li>
              ))}
            </ul>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
              <span className="font-semibold">
                {t("cart.total")}: {price(o.total_egp)}
              </span>
              {o.next_status &&
                (confirming === o.id ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-primary !py-2"
                      disabled={advance.isPending}
                      onClick={() =>
                        advance.mutate({ id: o.id, to: o.next_status! }, { onSettled: () => setConfirming(null) })
                      }
                    >
                      {fill(t("sel.confirmMove"), { step: t(MOVE_LABEL[o.next_status]) })}
                    </button>
                    <button type="button" className="btn-ghost !py-2" onClick={() => setConfirming(null)}>
                      {t("addr.cancel")}
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn-dark !py-2"
                    onClick={() => {
                      advance.reset();
                      setConfirming(o.id);
                    }}
                  >
                    {t(MOVE_LABEL[o.next_status])}
                  </button>
                ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
