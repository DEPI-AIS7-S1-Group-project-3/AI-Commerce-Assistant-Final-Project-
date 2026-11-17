import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";
import type { CheckoutProblem, PaymentMethod, Product } from "@/types";
import { ApiError, USE_MOCK } from "@/api/config";
import { getProduct } from "@/api/products";
import { checkout } from "@/api/orders";
import { useCart } from "@/hooks/useCart";
import { useAddresses, useAddressMutations } from "@/hooks/useAddresses";
import { useI18n, type TKey } from "@/lib/i18n";
import { fill, formatPrice } from "@/lib/format";
import { productTitle, sellerName } from "@/lib/productText";
import { FREE_FROM, shippingFor } from "@/lib/shipping";
import AddressForm from "@/components/AddressForm";
import AddressText from "@/components/AddressText";

const STEPS: TKey[] = ["co.step.address", "co.step.payment", "co.step.review"];
const METHODS: { id: PaymentMethod; label: TKey }[] = [
  { id: "cod", label: "co.pay.cod" },
  { id: "wallet", label: "co.pay.wallet" },
  { id: "card", label: "co.pay.card" },
];

export default function CheckoutPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { lines, refresh } = useCart();
  const addresses = useAddresses();
  const { create } = useAddressMutations();

  const [step, setStep] = useState(0);
  const [addressId, setAddressId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [method, setMethod] = useState<PaymentMethod>("cod");
  const [placing, setPlacing] = useState(false);
  const [problems, setProblems] = useState<CheckoutProblem[] | null>(null);
  const [failed, setFailed] = useState(false);

  // Preselect the default address (the backend lists it first).
  useEffect(() => {
    if (addressId === null && addresses.data?.length) setAddressId(addresses.data[0].id);
  }, [addresses.data, addressId]);

  const results = useQueries({
    queries: lines.map((l) => ({ queryKey: ["product", l.product_id], queryFn: () => getProduct(l.product_id) })),
  });

  if (USE_MOCK) return <p className="chip-neon">{t("addr.mockOnly")}</p>;
  if (lines.length === 0) {
    return (
      <div className="card mx-auto max-w-xl space-y-3 p-10 text-center">
        <h1 className="text-3xl">{t("cart.empty")}</h1>
        <Link to="/products" className="btn-primary">
          {t("cart.continue")}
        </Link>
      </div>
    );
  }

  const price = (n: number) => formatPrice(n, lang);
  const address = addresses.data?.find((a) => a.id === addressId);
  const rows = lines.map((line, i) => ({ line, product: results[i]?.data ?? null }));

  // Group by seller, one future order each (same rule as the backend).
  const groups = new Map<number, { name: string; items: { p: Product; qty: number }[]; subtotal: number }>();
  rows.forEach(({ line, product }) => {
    if (!product) return;
    const g = groups.get(product.seller.id) ?? { name: sellerName(product.seller, lang), items: [], subtotal: 0 };
    g.items.push({ p: product, qty: line.qty });
    g.subtotal += product.price_egp * line.qty;
    groups.set(product.seller.id, g);
  });
  const sellerGroups = [...groups.values()].map((g) => ({ ...g, fee: shippingFor(g.subtotal) }));
  const shipping = sellerGroups.reduce((s, g) => s + g.fee, 0);
  const total = sellerGroups.reduce((s, g) => s + g.subtotal, 0) + shipping;
  const many = sellerGroups.length > 1;
  const isolate = (s: string) => `\u2068${s}\u2069`; // keep Arabic names in order inside English text
  const titleOf = (id: number) => {
    const p = rows.find((r) => r.product?.id === id)?.product;
    return p ? productTitle(p, lang) : `#${id}`;
  };

  const place = async () => {
    if (!addressId) return;
    setPlacing(true);
    setProblems(null);
    setFailed(false);
    try {
      const result = await checkout(addressId, method);
      await refresh(); // the backend emptied the cart
      navigate("/orders/confirmation", { replace: true, state: result });
    } catch (e) {
      if (e instanceof ApiError && e.code === "checkout_unavailable") setProblems(e.details as CheckoutProblem[]);
      else if (e instanceof ApiError && e.code === "address_not_found") setStep(0);
      else setFailed(true);
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl">{t("co.title")}</h1>

      <ol className="flex gap-2" aria-label={t("co.title")}>
        {STEPS.map((s, i) => (
          <li key={s} className={`flex flex-1 items-center gap-2 rounded-ctl border-2 px-3 py-2 text-sm ${i === step ? "border-accent font-semibold" : "border-line text-ink-soft"}`} aria-current={i === step ? "step" : undefined}>
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sand text-xs" dir="ltr">
              {i < step ? <Check className="h-3.5 w-3.5 text-accent" aria-hidden /> : i + 1}
            </span>
            {t(s)}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <section className="space-y-4">
          {addresses.isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
          {addresses.isError && <p className="text-danger">{t("addr.loadErr")}</p>}
          <div className="space-y-3" role="radiogroup" aria-label={t("co.step.address")}>
            {addresses.data?.map((a) => (
              <label key={a.id} className={`card flex cursor-pointer items-start gap-3 p-4 ${a.id === addressId ? "!border-accent" : ""}`}>
                <input type="radio" name="address" className="mt-1 accent-green" checked={a.id === addressId} onChange={() => setAddressId(a.id)} />
                <AddressText a={a} />
              </label>
            ))}
          </div>
          {adding ? (
            <AddressForm
              onSubmit={async (d) => {
                const created = await create.mutateAsync(d);
                setAddressId(created.id);
                setAdding(false);
              }}
              onCancel={() => setAdding(false)}
            />
          ) : (
            <button type="button" className="btn-ghost" onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              {t("addr.add")}
            </button>
          )}
          <div className="flex justify-end">
            <button type="button" className="btn-primary" disabled={!addressId} onClick={() => setStep(1)}>
              {t("co.next")}
            </button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="space-y-4">
          <div className="space-y-3" role="radiogroup" aria-label={t("co.step.payment")}>
            {METHODS.map((m) => (
              <label key={m.id} className={`card flex cursor-pointer items-center gap-3 p-4 ${m.id === method ? "!border-accent" : ""}`}>
                <input type="radio" name="method" className="accent-green" checked={m.id === method} onChange={() => setMethod(m.id)} />
                {t(m.label)}
              </label>
            ))}
          </div>
          <p className="text-xs text-ink-soft">{t("co.pay.simulated")}</p>
          <div className="flex justify-between">
            <button type="button" className="btn-ghost" onClick={() => setStep(0)}>
              {t("co.back")}
            </button>
            <button type="button" className="btn-primary" onClick={() => setStep(2)}>
              {t("co.next")}
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="card space-y-2 p-4">
              <h2 className="text-sm text-ink-soft">{t("co.shipTo")}</h2>
              {address && <AddressText a={address} />}
            </div>
            <div className="card space-y-2 p-4">
              <h2 className="text-sm text-ink-soft">{t("co.payWith")}</h2>
              <p className="font-semibold">{t(METHODS.find((m) => m.id === method)!.label)}</p>
            </div>
          </div>

          {many && <p className="text-xs text-ink-soft">{t("co.splitNote")}</p>}
          {sellerGroups.map((g, i) => (
            <div key={g.name} className="card space-y-2 p-4">
              {many && (
                <h2 className="text-sm font-semibold">
                  {fill(t("co.package"), { i: i + 1, n: sellerGroups.length })}{" "}
                  <span className="font-normal text-ink-soft">{fill(t("co.fromSeller"), { seller: isolate(g.name) })}</span>
                </h2>
              )}
              <ul className="space-y-1 text-sm">
                {g.items.map(({ p, qty }) => (
                  <li key={p.id} className="flex justify-between gap-3">
                    <span>
                      <bdi>{productTitle(p, lang)}</bdi> <span className="text-ink-soft" dir="ltr">× {qty}</span>
                    </span>
                    <span>{price(p.price_egp * qty)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-ink-soft">{t("cart.shipping")}</span>
              <span className={shipping === 0 ? "text-accent" : ""}>{shipping === 0 ? t("cart.shipping.free") : price(shipping)}</span>
            </div>
            {sellerGroups
              .filter((g) => g.fee > 0)
              .map((g) => (
                <p key={g.name} className="text-xs text-ink-soft">
                  {fill(t("cart.freeHint"), { amount: price(FREE_FROM - g.subtotal), seller: isolate(g.name) })}
                </p>
              ))}
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-ink-soft">{t("cart.total")}</span>
            <span className="font-display text-2xl">{price(total)}</span>
          </div>

          {problems && (
            <div className="space-y-2 rounded-ctl border border-danger p-4 text-sm" role="alert">
              <p className="text-danger">{t("co.err.unavailable")}</p>
              <ul className="list-disc ps-5">
                {problems.map((pr) => (
                  <li key={pr.product_id}>
                    <bdi>{titleOf(pr.product_id)}</bdi>:{" "}
                    {pr.reason === "insufficient_stock" ? fill(t("co.err.available"), { n: pr.available ?? 0 }) : t("co.err.gone")}
                  </li>
                ))}
              </ul>
              <Link to="/cart" className="font-semibold text-accent hover:underline">
                {t("co.err.toCart")}
              </Link>
            </div>
          )}
          {failed && <p className="text-sm text-danger" role="alert">{t("co.err.generic")}</p>}

          <div className="flex justify-between">
            <button type="button" className="btn-ghost" onClick={() => setStep(1)} disabled={placing}>
              {t("co.back")}
            </button>
            <button type="button" className="btn-primary" onClick={place} disabled={placing || !address}>
              {placing ? t("co.placing") : t("co.place")}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
