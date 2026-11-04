import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { USE_MOCK, ApiError, emailOk, passwordOk, phoneOk } from "@/api/auth";
import { useAuth } from "@/hooks/useAuth";
import { useI18n, type TKey } from "@/lib/i18n";

export default function RegisterPage() {
  const { t } = useI18n();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState<TKey | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const validate = (): TKey | null => {
    if (form.full_name.trim().length < 2) return "auth.v.name";
    if (!emailOk(form.email.trim())) return "auth.v.email";
    if (!phoneOk(form.phone.trim())) return "auth.v.phone";
    if (!passwordOk(form.password)) return "auth.v.password";
    return null;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validate();
    if (v) return setError(v);
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, full_name: form.full_name.trim(), email: form.email.trim(), phone: form.phone.trim() });
      navigate("/", { replace: true });
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "generic";
      const key = `auth.err.${code}` as TKey;
      setError(
        ["auth.err.email_taken", "auth.err.role_not_allowed", "auth.err.network"].includes(key) ? key : "auth.err.generic",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6 py-6">
      <h1 className="text-4xl">{t("auth.register")}</h1>
      {USE_MOCK && <p className="chip-neon">{t("auth.mock")}</p>}
      <form onSubmit={onSubmit} className="card space-y-4 p-6" noValidate>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.name")}</span>
          <input className="input" autoComplete="name" value={form.full_name} onChange={set("full_name")} />
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.email")}</span>
          <input className="input" dir="ltr" type="email" autoComplete="email" value={form.email} onChange={set("email")} />
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.phone")}</span>
          <input className="input" dir="ltr" inputMode="numeric" autoComplete="tel" value={form.phone} onChange={set("phone")} />
          <span className="text-xs text-ink-soft">{t("auth.phone.hint")}</span>
        </label>
        <label className="block space-y-1 text-sm">
          <span>{t("auth.password")}</span>
          <input className="input" dir="ltr" type="password" autoComplete="new-password" value={form.password} onChange={set("password")} />
          <span className="text-xs text-ink-soft">{t("auth.password.hint")}</span>
        </label>
        {error && (
          <p className="text-sm text-danger" role="alert">
            {t(error)}
          </p>
        )}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? t("auth.loading") : t("auth.register")}
        </button>
      </form>
      <p className="text-sm text-ink-soft">
        {t("auth.haveaccount")}{" "}
        <Link to="/login" className="font-semibold text-neon hover:underline">
          {t("auth.login")}
        </Link>
      </p>
    </div>
  );
}