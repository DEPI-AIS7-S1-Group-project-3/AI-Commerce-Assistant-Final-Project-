import { Link, useLocation } from "react-router-dom";
import { CircleCheck } from "lucide-react";
import type { CheckoutResult } from "@/types";
import { useI18n } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import AddressText from "@/components/AddressText";

// Shown right after checkout. The backend creates one order per seller; the customer sees
// ONE confirmed order that arrives in one or more packages (each package = one backend order).
// The result arrives via router state; the orders list/detail pages come in step 14.
export default function OrderConfirmationPage() {
  const { t, lang } = useI18n();
  const result = useLocation().state as CheckoutResult | null;

  if (!result?.orders?.length) {
    return (
      <div className="card mx-auto max-w-xl space-y-3 p-10 text-center">
        <p>{t("oc.missing")}</p>
        <Link to="/products" className="btn-primary">
          {t("oc.continue")}
        </Link>
      </div>
    );
  }

  const orders = result.orders;
  const n = orders.length;
  const price = (v: number) => formatPrice(v, lang);
  const total = orders.reduce((s, o) => s + o.total_egp, 0);
  const shipping = orders.reduce((s, o) => s + o.shipping_fee_egp, 0);
  const paid = orders.every((o) => o.payment_status === "paid");
  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2 text-center">
        <CircleCheck className="mx-auto h-12 w-12 text-accent" aria-hidden />
        <h1 className="text-3xl">{t("oc.title")}</h1>
        {n > 1 && <p className="text-ink-soft">{n === 2 ? t("oc.packages.two") : fill(t("oc.packages.many"), { n })}</p>}
      </header>

      {orders.map((o, i) => (
        <div key={o.id} className="card space-y-3 p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            {n > 1 && <h2 className="font-semibold">{fill(t("co.package"), { i: i + 1, n })}</h2>}
            <Link to={`/orders/${o.id}`} className="text-xs text-ink-soft hover:text-accent" dir="auto">
              {fill(t("oc.order"), { id: o.id })}
            </Link>
          </div>
          <ul className="space-y-1 text-sm">
            {o.items.map((it) => (
              <li key={it.product_id} className="flex justify-between gap-3">
                <span>
                  <bdi>{it.title}</bdi> <span className="text-ink-soft" dir="ltr">× {it.qty}</span>
                </span>
                <span>{price(it.line_total_egp)}</span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-accent">{fill(t("oc.delivery"), { date: date(o.expected_delivery_at) })}</p>
        </div>
      ))}

      <div className="card space-y-2 p-5 text-sm">
        <div className="flex justify-between">
          <span className="text-ink-soft">{t("cart.shipping")}</span>
          <span>{shipping === 0 ? t("cart.shipping.free") : price(shipping)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-base font-semibold">{t("cart.total")}</span>
          <span className="flex items-center gap-2">
            <span className={paid ? "chip-neon" : "chip"}>{paid ? t("oc.paid") : t("oc.pending")}</span>
            <span className="font-display text-xl">{price(total)}</span>
          </span>
        </div>
        <div className="border-t border-line pt-3">
          <AddressText a={orders[0].shipping_address} />
        </div>
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <Link to="/orders" className="btn-ghost">
          {t("oc.viewOrders")}
        </Link>
        <Link to="/products" className="btn-primary">
          {t("oc.continue")}
        </Link>
      </div>
    </div>
  );
}
