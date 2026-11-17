import { type FormEvent, useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, LogIn, LogOut, MapPin, Menu, Package, Search, ShoppingBag, Sparkles, Store, X } from "lucide-react";
import { useCart } from "@/hooks/useCart";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/lib/i18n";
import Logo from "./Logo";
import LanguageSwitch from "./LanguageSwitch";
import ThemeSwitch from "./ThemeSwitch";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium transition-colors ${isActive ? "text-accent" : "text-ink-soft hover:text-ink"}`;

// Desktop (lg and up): one row, as before.
// Below lg: row 1 = logo, assistant icon, cart, menu button; row 2 = full-width search;
// the menu opens a panel with every other link.
export default function Navbar() {
  const { count } = useCart();
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);

  // Close the menu when the page changes or Escape is pressed.
  useEffect(() => setOpen(false), [location.pathname, location.search]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = term.trim();
    navigate(q ? `/products?q=${encodeURIComponent(q)}` : "/products");
  };

  const searchForm = (className: string) => (
    <form onSubmit={onSearch} role="search" className={`relative ${className}`}>
      <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" aria-hidden />
      <input value={term} onChange={(e) => setTerm(e.target.value)} className="input ps-9" placeholder={t("nav.search")} aria-label={t("nav.search")} />
    </form>
  );

  const cartButton = (
    <Link to="/cart" className="btn-ghost relative !px-3 !py-2" aria-label={`${t("nav.cart")} (${count})`}>
      <ShoppingBag className="h-4 w-4" aria-hidden />
      <span className="hidden lg:inline">{t("nav.cart")}</span>
      {count > 0 && (
        <span className="inline-flex min-w-5 items-center justify-center rounded-ctl bg-neon px-1 text-xs font-semibold leading-5 text-on-neon">
          {count}
        </span>
      )}
    </Link>
  );

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur">
      {/* ---------- desktop ---------- */}
      <div className="mx-auto hidden max-w-7xl items-center gap-6 px-6 py-3 lg:flex">
        <Logo />
        <Link to="/assistant" className="btn-primary !px-4 !py-2">
          <Sparkles className="h-4 w-4" aria-hidden />
          {t("nav.assistant")}
        </Link>
        <nav className="flex items-center gap-6" aria-label={t("nav.main")}>
          <NavLink to="/products" className={linkClass}>
            {t("nav.shop")}
          </NavLink>
        </nav>
        {searchForm("ms-auto max-w-md flex-1")}
        <div className="flex items-center gap-2">
          <ThemeSwitch />
          <LanguageSwitch />
          {cartButton}
          {user ? (
            <div className="inline-flex items-center gap-2">
              {user.role === "seller" ? (
                <Link to="/seller" className="text-sm font-medium text-ink-soft hover:text-accent">
                  {t("nav.seller")}
                </Link>
              ) : (
                <Link to="/orders" className="text-sm font-medium text-ink-soft hover:text-accent">
                  {t("nav.orders")}
                </Link>
              )}
              <Link to="/addresses" className="max-w-[120px] truncate text-sm font-medium text-ink hover:text-accent" title={t("nav.addresses")}>
                {user.full_name.split(" ")[0]}
              </Link>
              <button type="button" onClick={logout} className="btn-ghost !px-2.5 !py-1.5 text-xs text-ink-soft hover:text-danger">
                {t("auth.logout")}
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn-dark !py-2">
              {t("nav.login")}
            </Link>
          )}
        </div>
      </div>

      {/* ---------- phones + tablets ---------- */}
      <div className="space-y-3 px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2">
          <Logo />
          <div className="ms-auto flex items-center gap-2">
            <Link to="/assistant" className="btn-primary !p-2" aria-label={t("nav.assistant")} title={t("nav.assistant")}>
              <Sparkles className="h-4 w-4" aria-hidden />
            </Link>
            {cartButton}
            <button
              type="button"
              className="btn-ghost !p-2"
              aria-expanded={open}
              aria-controls="mobile-menu"
              aria-label={open ? t("nav.close") : t("nav.menu")}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X className="h-5 w-5" aria-hidden /> : <Menu className="h-5 w-5" aria-hidden />}
            </button>
          </div>
        </div>
        {searchForm("w-full")}
      </div>

      {open && (
        <nav id="mobile-menu" aria-label={t("nav.main")} className="border-t border-line bg-paper px-4 pb-4 pt-2 lg:hidden">
          <ul className="divide-y divide-line">
            <MenuItem to="/assistant" icon={Sparkles} label={t("nav.assistant")} />
            <MenuItem to="/products" icon={Store} label={t("nav.shop")} />
            {user?.role === "seller" && <MenuItem to="/seller" icon={LayoutDashboard} label={t("nav.seller")} />}
            {user?.role === "seller" && <MenuItem to="/seller/orders" icon={Package} label={t("sel.orders.nav")} />}
            {user && user.role !== "seller" && <MenuItem to="/orders" icon={Package} label={t("nav.orders")} />}
            {user && user.role !== "seller" && <MenuItem to="/addresses" icon={MapPin} label={t("nav.addresses")} />}
            {user ? (
              <li>
                <button type="button" onClick={logout} className="flex w-full items-center gap-3 py-3 text-sm font-medium text-ink-soft hover:text-danger">
                  <LogOut className="h-4 w-4" aria-hidden />
                  {t("auth.logout")}
                  <span className="ms-auto max-w-[50%] truncate text-xs">{user.full_name}</span>
                </button>
              </li>
            ) : (
              <MenuItem to="/login" icon={LogIn} label={t("nav.login")} />
            )}
          </ul>
          <div className="flex items-center gap-2 pt-3">
            <ThemeSwitch />
            <LanguageSwitch />
          </div>
        </nav>
      )}
    </header>
  );
}

function MenuItem({ to, icon: Icon, label }: { to: string; icon: typeof Store; label: string }) {
  return (
    <li>
      <NavLink to={to} className={({ isActive }) => `flex items-center gap-3 py-3 text-sm font-medium ${isActive ? "text-accent" : "text-ink hover:text-accent"}`}>
        <Icon className="h-4 w-4" aria-hidden />
        {label}
      </NavLink>
    </li>
  );
}
