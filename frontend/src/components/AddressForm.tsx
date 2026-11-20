import { type FormEvent, type ReactNode, useState } from "react";
import type { Address, AddressInput } from "@/types";
import { phoneOk } from "@/api/auth";
import { useI18n, type TKey } from "@/lib/i18n";
import { GOVERNORATES } from "@/lib/governorates";

type Props = {
  initial?: Address;
  onSubmit: (data: AddressInput) => Promise<void>;
  onCancel?: () => void;
};

const EMPTY: AddressInput = {
  label: null,
  recipient_name: "",
  phone: "",
  governorate: "",
  city: "",
  street_address: "",
  is_default: false,
};

// Same rules as the backend (schemas/address.py): required fields not blank, Egyptian mobile.
export default function AddressForm({ initial, onSubmit, onCancel }: Props) {
  const { t, lang } = useI18n();
  const [d, setD] = useState<AddressInput>(initial ? { ...initial } : EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof AddressInput, TKey>>>({});
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<AddressInput>) => setD((cur) => ({ ...cur, ...patch }));

  const validate = () => {
    const e: typeof errors = {};
    for (const k of ["recipient_name", "governorate", "city", "street_address"] as const) {
      if (!d[k].trim()) e[k] = "addr.v.required";
    }
    if (!phoneOk(d.phone)) e.phone = "auth.v.phone";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setBusy(true);
    setFailed(false);
    try {
      await onSubmit({ ...d, label: d.label?.trim() || null });
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const field = (k: keyof AddressInput, label: TKey, input: ReactNode) => (
    <label className="block space-y-1 text-sm">
      <span>{t(label)}</span>
      {input}
      {errors[k] && <span className="block text-xs text-danger">{t(errors[k]!)}</span>}
    </label>
  );

  return (
    <form onSubmit={submit} className="card space-y-4 p-5" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        {field("recipient_name", "addr.recipient", <input className="input" autoComplete="name" value={d.recipient_name} onChange={(e) => set({ recipient_name: e.target.value })} />)}
        {field("phone", "addr.phone", <input className="input" dir="ltr" inputMode="tel" autoComplete="tel" placeholder="01012345678" value={d.phone} onChange={(e) => set({ phone: e.target.value.replace(/\s/g, "") })} />)}
        {field(
          "governorate",
          "addr.governorate",
          <select className="input" value={d.governorate} onChange={(e) => set({ governorate: e.target.value })}>
            <option value="">{t("addr.chooseGov")}</option>
            {GOVERNORATES.map((g) => (
              <option key={g.ar} value={g.ar}>
                {lang === "en" ? g.en : g.ar}
              </option>
            ))}
          </select>,
        )}
        {field("city", "addr.city", <input className="input" value={d.city} onChange={(e) => set({ city: e.target.value })} />)}
      </div>
      {field("street_address", "addr.street", <textarea className="input min-h-20" value={d.street_address} onChange={(e) => set({ street_address: e.target.value })} />)}
      {field("label", "addr.label", <input className="input" placeholder={t("addr.label.hint")} maxLength={50} value={d.label ?? ""} onChange={(e) => set({ label: e.target.value })} />)}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="accent-green" checked={d.is_default} onChange={(e) => set({ is_default: e.target.checked })} />
        {t("addr.makeDefault")}
      </label>
      {failed && <p className="text-sm text-danger" role="alert">{t("addr.err")}</p>}
      <div className="flex gap-3">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? t("auth.loading") : t("addr.save")}
        </button>
        {onCancel && (
          <button type="button" className="btn-ghost" onClick={onCancel}>
            {t("addr.cancel")}
          </button>
        )}
      </div>
    </form>
  );
}
