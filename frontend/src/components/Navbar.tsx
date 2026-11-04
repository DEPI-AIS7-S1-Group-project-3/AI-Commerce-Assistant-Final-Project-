import { FormEvent, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Search, ShoppingBag, Sparkles } from "lucide-react";
import { useCart } from "@/hooks/useCart";
import { useI18n } from "@/lib/i18n";
import Logo from "./Logo";
import LanguageSwitch from "./LanguageSwitch";
import { useAuth } from "@/hooks/useAuth";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium transition-colors ${isActive ? "text-neon" : "text-ink-soft hover:text-ink"}`;

export default function Navbar() {
  const { count } = useCart();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [term, setTerm] = useState("");

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = term.trim();
    navigate(q ? `/products?q=${encodeURIComponent(q)}` : "/products");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:gap-6 sm:px-6">
        <Logo />

        <Link to="/assistant" className="btn-primary !px-4 !py-2">
          <Sparkles className="h-4 w-4" aria-hidden />
          {t("nav.assistant")}
        </Link>

        <nav className="hidden items-center gap-6 md:flex" aria-label={t("nav.main")}>
          <NavLink to="/products" className={linkClass}>
            {t("nav.shop")}
          </NavLink>
        </nav>

        <form onSubmit={onSearch} role="search" className="relative ms-auto hidden max-w-md flex-1 lg:block">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" aria-hidden />
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            className="input ps-9"
            placeholder={t("nav.search")}
            aria-label={t("nav.search")}
          />
        </form>

        <div className="ms-auto flex items-center gap-2 lg:ms-0">
          <LanguageSwitch />
          <Link to="/cart" className="btn-ghost relative !px-3 !py-2" aria-label={`${t("nav.cart")} (${count})`}>
            <ShoppingBag className="h-4 w-4" aria-hidden />
            <span className="hidden sm:inline">{t("nav.cart")}</span>
            {count > 0 && (
              <span className="inline-flex min-w-5 items-center justify-center rounded-ctl bg-neon px-1 text-xs font-semibold leading-5 text-paper">
                {count}
              </span>
            )}
          </Link>
          <Link to="/login" className="btn-dark hidden !py-2 sm:inline-flex">
            {t("nav.login")}
          </Link>
        </div>
      </div>
    </header>
  );
}