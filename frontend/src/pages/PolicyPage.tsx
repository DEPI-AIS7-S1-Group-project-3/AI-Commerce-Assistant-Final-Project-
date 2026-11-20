import { Link, NavLink, Navigate, useParams } from "react-router-dom";
import { usePolicies, usePolicy } from "@/hooks/usePolicies";
import { useI18n, type TKey } from "@/lib/i18n";
import { fill } from "@/lib/format";
import MiniMarkdown from "@/components/MiniMarkdown";

// English tab labels (the policy text itself is Arabic only).
const LABEL: Record<string, TKey> = {
  shipping: "policy.shipping",
  returns: "policy.returns",
  warranty: "policy.warranty",
  cancellation: "policy.cancellation",
};

/** Text before the first "## n." heading, without the "# title" line (e.g. the demo notice). */
const intro = (md: string) =>
  md
    .split(/^##\s+\d+\./m)[0]
    .split("\n")
    .filter((l) => !l.trim().startsWith("# "))
    .join("\n");

export default function PolicyPage() {
  const { slug = "" } = useParams();
  const { t, lang } = useI18n();
  const list = usePolicies();
  const { data: policy, isLoading, isError, refetch } = usePolicy(slug);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <h1 className="text-3xl">{t("pol.title")}</h1>

      <nav aria-label={t("pol.title")} className="flex gap-2 overflow-x-auto border-b border-line pb-3">
        {(list.data ?? []).map((p) => (
          <NavLink
            key={p.slug}
            to={`/policies/${p.slug}`}
            className={({ isActive }) =>
              `shrink-0 rounded-ctl px-3 py-2 text-sm font-medium ${isActive ? "bg-neon text-on-neon" : "text-ink-soft hover:text-ink"}`
            }
          >
            {lang === "en" && LABEL[p.slug] ? t(LABEL[p.slug]) : p.title_ar}
          </NavLink>
        ))}
      </nav>

      {isLoading && <p className="text-ink-soft">{t("cart.loading")}...</p>}
      {isError && (
        <div className="space-y-2">
          <p className="text-danger">{t("pol.loadErr")}</p>
          <button type="button" className="btn-dark" onClick={() => refetch()}>
            {t("products.retry")}
          </button>
        </div>
      )}
      {!isLoading && !isError && !policy && (
        <div className="space-y-3">
          <p>{t("pol.notfound")}</p>
          <Link to="/policies/shipping" className="btn-dark">
            {t("policy.shipping")}
          </Link>
        </div>
      )}

      {policy && (
        <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
          <aside className="space-y-2 lg:sticky lg:top-28 lg:self-start">
            <h2 className="text-sm text-ink-soft">{t("pol.contents")}</h2>
            <ol className="space-y-1 text-sm" dir="rtl" lang="ar">
              {policy.sections.map((s) => (
                <li key={s.no}>
                  <a href={`#s-${s.no}`} className="hover:text-accent">
                    {s.no}. {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </aside>

          <article className="space-y-6">
            {lang === "en" && <p className="chip">{t("pol.arabicOnly")}</p>}
            <div dir="rtl" lang="ar" className="space-y-6">
              <header className="space-y-2">
                <h2 className="text-2xl">{policy.title_ar}</h2>
                <MiniMarkdown md={intro(policy.body_md)} />
              </header>
              {policy.sections.map((s) => (
                <section key={s.no} id={`s-${s.no}`} className="scroll-mt-28 space-y-2">
                  <h3 className="text-lg">
                    {s.no}. {s.title}
                  </h3>
                  <MiniMarkdown md={s.body} />
                </section>
              ))}
            </div>
            <p className="text-xs text-ink-soft">{fill(t("pol.version"), { v: policy.version })}</p>
          </article>
        </div>
      )}
    </div>
  );
}

export const PoliciesIndex = () => <Navigate to="/policies/shipping" replace />;
