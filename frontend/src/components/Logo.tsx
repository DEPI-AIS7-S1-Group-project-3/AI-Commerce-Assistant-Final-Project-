import { Link } from "react-router-dom";
import { useI18n } from "@/lib/i18n";

// Bilingual wordmark.
// sm and up: "kashida" version. The tatweel stretches دكان and DOKKAN TECH sits in the
//   gap above the stretched line. Offsets are in em of the Arabic size (measured in the
//   browser with Kufam 700), so they scale with it. 13 tatweels = room for the Latin.
// Phones: "stacked" version (Latin spread under the Arabic), easier to read small.
// Always laid out right-to-left so it reads "دكان تك" in both languages.
export default function Logo() {
  const { t } = useI18n();
  return (
    <Link to="/" className="inline-flex shrink-0" aria-label={t("logo.home")}>
      <span dir="rtl" aria-hidden className="relative hidden font-display text-[30px] font-bold leading-none sm:inline-block">
        <span className="text-ink">{"دك" + "ـ".repeat(13) + "ان"}</span> <span className="text-accent">تك</span>
        <span className="absolute left-[2.82em] right-[1.95em] top-[0.27em] flex justify-center" dir="ltr">
          <span className="whitespace-nowrap text-[9px] leading-none tracking-[0.14em] text-accent">DOKKAN TECH</span>
        </span>
      </span>

      <span aria-hidden className="inline-flex flex-col items-stretch gap-1 sm:hidden">
        <span dir="rtl" className="text-center font-display text-2xl font-bold leading-none text-ink">
          دكان <span className="text-accent">تك</span>
        </span>
        <span className="h-[3px] bg-accent" />
        <span dir="ltr" className="text-center font-display text-[10px] font-bold leading-none tracking-[0.42em] text-ink-soft">
          DOKKAN TECH
        </span>
      </span>
    </Link>
  );
}
