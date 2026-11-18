import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check } from "lucide-react";
import type { OrderDetail, OrderItem, ReturnReason } from "@/types";
import { ApiError, USE_MOCK } from "@/api/config";
import { useOrder, useOrderActions } from "@/hooks/useOrders";
import { useI18n, type TKey } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { RETURN_WINDOW_DAYS, blockKey, fmtDate, statusClass, statusKey } from "@/lib/orders";
import AddressText from "@/components/AddressText";

const REASONS: ReturnReason[] = ["defective", "not_as_described", "wrong_item", "damaged_in_shipping", "changed_mind", "other"];
const PAYMENT: Record<string, TKey> = { cod: "co.pay.cod", wallet: "co.pay.wallet", card: "co.pay.card" };

// One backend order = one package. Cancel and return buttons follow the flags the backend
// computes (can_cancel / can_return); the backend re-checks on every action anyway.
export default function OrderDetailPage() {
  const { id } = useParams();
  const orderId = Number(id);
  const valid = Number.isInteger(orderId) && orderId > 0;
  const { t } = useI18n();
  const { data, isLoading, isError, error } = useOrder(valid ? orderId : -1);

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;
  const notFound = !valid || (isError && error instanceof ApiError && error.status === 404);
  if (notFound) {
    return (
      <section className="mx-auto max-w-md space-y-4 py-20 text-center">
        <h1 className="text-3xl">{t("ord.notfound")}</h1>
        <Link to="/orders" className="btn-dark">
          {t("ord.back")}
        </Link>
      </section>
    );
  }
  if (isError) return <p className="text-danger">{t("ord.loadErr")}</p>;
  if (isLoading || !data) return <p className="text-ink-soft">{t("cart.loading")}...</p>;
  return <OrderView order={data} />;
}

function OrderView({ order }: { order: OrderDetail }) {
  const { t, lang } = useI18n();
  const { cancel } = useOrderActions(order.id);
  const [confirming, setConfirming] = useState(false);
  const price = (n: number) => formatPrice(n, lang);
  const cancelError = cancel.error instanceof ApiError ? blockKey(cancel.error.code) : cancel.error ? "ord.err.generic" : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/orders" className="text-sm text-accent hover:underline">
        {t("ord.back")}
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-5">
        <div className="space-y-1">
          <h1 className="text-3xl" dir="auto">
            {fill(t("oc.order"), { id: order.id })}
          </h1>
          <p className="text-sm text-ink-soft">
            {fill(t("ord.placedOn"), { date: fmtDate(order.created_at, lang) })} · <bdi>{order.seller_name}</bdi>
          </p>
        </div>
        <span className={statusClass(order.status)}>{t(statusKey(order.status))}</span>
      </header>

      <p className="text-sm text-accent">
        {order.delivered_at
          ? fill(t("ord.deliveredOn"), { date: fmtDate(order.delivered_at, lang) })
          : order.status !== "cancelled" && fill(t("ord.expected"), { date: fmtDate(order.expected_delivery_at, lang, true) })}
      </p>

      <ul className="space-y-3">
        {order.items.map((it) => (
          <ItemRow key={it.id} order={order} item={it} />
        ))}
      </ul>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="card space-y-3 p-5">
          <h2 className="text-lg">{t("ord.timeline")}</h2>
          <ol className="space-y-3">
            {order.timeline.map((e, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-on-neon">
                  <Check className="h-3 w-3" aria-hidden />
                </span>
                <div>
                  <p className="font-medium">{t(statusKey(e.to_status))}</p>
                  <p className="text-xs text-ink-soft">{fmtDate(e.created_at, lang)}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="card space-y-3 p-5 text-sm">
          <h2 className="text-lg">{t("ord.summary")}</h2>
          <Row label={t("ord.subtotal")} value={price(order.subtotal_egp)} />
          <Row label={t("cart.shipping")} value={order.shipping_fee_egp === 0 ? t("cart.shipping.free") : price(order.shipping_fee_egp)} />
          <Row label={t("cart.total")} value={price(order.total_egp)} strong />
          <Row
            label={t(PAYMENT[order.payment_method] ?? "co.payWith")}
            value={order.payment_status === "paid" ? t("oc.paid") : t("oc.pending")}
          />
          <div className="border-t border-line pt-3">
            <AddressText a={order.shipping_address} />
          </div>
        </section>
      </div>

      {order.can_cancel ? (
        <section className="space-y-2">
          <p className="text-xs text-ink-soft">{t("ord.cancel.note")}</p>
          {confirming ? (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn !border-danger text-danger"
                disabled={cancel.isPending}
                onClick={() => cancel.mutate(undefined, { onSettled: () => setConfirming(false) })}
              >
                {t("ord.cancel.confirm")}
              </button>
              <button type="button" className="btn-ghost" onClick={() => setConfirming(false)}>
                {t("ord.cancel.keep")}
              </button>
            </div>
          ) : (
            <button type="button" className="btn-ghost hover:!border-danger hover:!text-danger" onClick={() => setConfirming(true)}>
              {t("ord.cancel")}
            </button>
          )}
        </section>
      ) : null}
      {cancelError && (
        <p className="text-sm text-danger" role="alert">
          {t(cancelError)}
        </p>
      )}
    </div>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 ${strong ? "font-semibold" : ""}`}>
      <span className={strong ? "" : "text-ink-soft"}>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function ItemRow({ order, item }: { order: OrderDetail; item: OrderItem }) {
  const { t, lang } = useI18n();
  const { requestReturn } = useOrderActions(order.id);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReturnReason | "">("");
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);

  const until =
    order.delivered_at && item.can_return
      ? new Date(new Date(order.delivered_at).getTime() + RETURN_WINDOW_DAYS * 86400000).toISOString()
      : null;
  const err =
    requestReturn.error instanceof ApiError ? blockKey(requestReturn.error.code) : requestReturn.error ? "ord.err.generic" : null;

  const submit = () => {
    if (!reason) {
      setInvalid(true);
      return;
    }
    requestReturn.mutate({ itemId: item.id, reason, text: note.trim() || null }, { onSuccess: () => setOpen(false) });
  };

  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-0.5">
          <Link to={`/products/${item.product_id}`} className="font-semibold hover:text-accent">
            <bdi>{item.title}</bdi>
          </Link>
          <p className="text-xs text-ink-soft" dir="auto">
            {item.qty} × {formatPrice(item.unit_price_egp, lang)}
          </p>
        </div>
        <span>{formatPrice(item.line_total_egp, lang)}</span>
      </div>

      {item.return_status ? (
        <p className="chip">{t(`rs.${item.return_status}` as TKey)}</p>
      ) : item.can_return ? (
        <div className="space-y-2">
          {until && <p className="text-xs text-ink-soft">{fill(t("ord.return.until"), { date: fmtDate(until, lang) })}</p>}
          {!open ? (
            <button type="button" className="btn-ghost !px-3 !py-2 text-xs" onClick={() => setOpen(true)}>
              {t("ord.return")}
            </button>
          ) : (
            <div className="space-y-3 rounded-ctl border border-line bg-sand p-3">
              <label className="block space-y-1 text-sm">
                <span>{t("ord.return.reason")}</span>
                <select
                  className="input"
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value as ReturnReason);
                    setInvalid(false);
                  }}
                >
                  <option value="">{t("ord.return.chooseReason")}</option>
                  {REASONS.map((r) => (
                    <option key={r} value={r}>
                      {t(`rr.${r}` as TKey)}
                    </option>
                  ))}
                </select>
                {invalid && <span className="block text-xs text-danger">{t("ord.return.v")}</span>}
              </label>
              <label className="block space-y-1 text-sm">
                <span>{t("ord.return.note")}</span>
                <textarea className="input min-h-16" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
              </label>
              <div className="flex gap-2">
                <button type="button" className="btn-primary !py-2" disabled={requestReturn.isPending} onClick={submit}>
                  {t("ord.return.confirm")}
                </button>
                <button type="button" className="btn-ghost !py-2" onClick={() => setOpen(false)}>
                  {t("addr.cancel")}
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        order.status === "delivered" &&
        item.return_block && <p className="text-xs text-ink-soft">{t(blockKey(item.return_block))}</p>
      )}
      {err && (
        <p className="text-sm text-danger" role="alert">
          {t(err)}
        </p>
      )}
    </li>
  );
}
