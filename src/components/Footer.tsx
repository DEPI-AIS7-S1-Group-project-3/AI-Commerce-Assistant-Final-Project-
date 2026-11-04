import { Link } from "react-router-dom";
import { useI18n, type TKey } from "@/lib/i18n";
import Logo from "./Logo";

const policies: { to: string; label: TKey }[] = [
  { to: "/policies/shipping", label: "policy.shipping" },
  { to: "/policies/returns", label: "policy.returns" },
  { to: "/policies/warranty", label: "policy.warranty" },
  { to: "/policies/cancellation", label: "policy.cancellation" },
];

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="mt-16 border-t border-line bg-sand">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-2 sm:px-6">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-sm text-sm text-ink-soft">{t("footer.desc")}</p>
        </div>
        <nav aria-label={t("footer.policies")}>
          <h2 className="mb-3 text-base">{t("footer.policies")}</h2>
          <ul className="grid grid-cols-2 gap-2 text-sm">
            {policies.map((p) => (
              <li key={p.to}>
                <Link to={p.to} className="text-ink-soft hover:text-neon">
                  {t(p.label)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <div className="border-t border-line py-4 text-center text-xs text-ink-soft">{t("footer.note")}</div>
    </footer>
  );
}