import { Link } from "react-router-dom";
import { useI18n } from "@/lib/i18n";

export default function NotFoundPage() {
  const { t } = useI18n();
  return (
    <section className="mx-auto max-w-md space-y-4 py-20 text-center">
      <h1 className="text-4xl">{t("notfound.title")}</h1>
      <p className="text-ink-soft">{t("notfound.body")}</p>
      <Link to="/" className="btn-dark">
        {t("notfound.home")}
      </Link>
    </section>
  );
}
