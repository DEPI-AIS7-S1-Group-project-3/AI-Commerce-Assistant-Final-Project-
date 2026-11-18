import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { useI18n } from "@/lib/i18n";

export default function ThemeSwitch() {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const label = t(theme === "dark" ? "theme.toLight" : "theme.toDark");
  return (
    <button type="button" onClick={toggle} className="btn-ghost !px-3 !py-2" aria-label={label} title={label}>
      {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </button>
  );
}
