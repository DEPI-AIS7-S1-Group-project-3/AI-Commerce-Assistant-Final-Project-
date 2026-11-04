import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { USE_MOCK, ApiError, emailOk } from "@/api/auth";
import { useAuth } from "@/hooks/useAuth";
import { useI18n, type TKey } from "@/lib/i18n";

export default function LoginPage() {
  const { t } = useI18n();
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<TKey | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!emailOk(email.trim()) || !password) return setError("auth.v.email");
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "generic";
      const key = `auth.err.${code}` as TKey;
      setError(["auth.err.invalid_credentials", "auth.err.network"].includes(key) ? key : "auth.err.generic");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6 py-6">
      <h1 className="text-4xl">{t("auth.login")}</h1>
      {USE_MOCK && <p className="chip-neon">{t("auth.mock")}</p>}
      <form onSubmit={onSubmit} className="card space-y-4 p-6" noValidate>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.email")}</span>
          <input className="input" dir="ltr" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.password")}</span>
          <input className="input" dir="ltr" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && (
          <p className="text-sm text-danger" role="alert">
            {t(error)}
          </p>
        )}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? t("auth.loading") : t("auth.login")}
        </button>
      </form>
      <p className="text-sm text-ink-soft">
        {t("auth.noaccount")}{" "}
        <Link to="/register" className="font-semibold text-neon hover:underline">
          {t("auth.register")}
        </Link>
      </p>
    </div>
  );
}