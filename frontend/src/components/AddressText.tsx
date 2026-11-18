import type { Address } from "@/types";
import { useI18n } from "@/lib/i18n";
import { governorateName } from "@/lib/governorates";

// Read-only address text (used in the address book, checkout and confirmation).
export default function AddressText({ a }: { a: Partial<Address> }) {
  const { lang } = useI18n();
  return (
    <div className="space-y-0.5 text-sm" dir="auto">
      <p className="font-semibold">
        {a.recipient_name}
        {a.label && <span className="ms-2 text-xs font-normal text-ink-soft">({a.label})</span>}
      </p>
      <p className="text-ink-soft">{a.street_address}</p>
      <p className="text-ink-soft">
        {[a.city, a.governorate && governorateName(a.governorate, lang)].filter(Boolean).join(lang === "ar" ? "، " : ", ")}
      </p>
      <p className="text-ink-soft" dir="ltr">
        {a.phone}
      </p>
    </div>
  );
}
