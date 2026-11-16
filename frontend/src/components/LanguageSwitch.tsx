import { Languages } from "lucide-react";
import { useI18n } from "../lib/i18n";

export default function LanguageSwitch() {
  const { toggle, t } = useI18n();
  return (
    <button type="button" onClick={toggle} className="btn-ghost !px-3 !py-2">
      <Languages size={18} aria-hidden />
      {t("lang.switch")}
    </button>
  );
}