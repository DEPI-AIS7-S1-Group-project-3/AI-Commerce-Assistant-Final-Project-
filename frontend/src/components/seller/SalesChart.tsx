import { useI18n } from "@/lib/i18n";
import { formatPrice } from "@/lib/format";

type Point = { day: string; revenue: number; orders: number };

// Hand-made SVG bar chart: one bar per day. Time always runs left -> right (also in Arabic),
// like most financial charts. Each bar has a <title> tooltip with the exact numbers.
export default function SalesChart({ data }: { data: Point[] }) {
  const { lang, t } = useI18n();
  const W = 640;
  const H = 200;
  const PAD = { top: 12, bottom: 24, left: 4, right: 4 };
  const max = Math.max(...data.map((d) => d.revenue), 1);
  const step = (W - PAD.left - PAD.right) / Math.max(data.length, 1);
  const bar = Math.max(step * 0.7, 2);
  const innerH = H - PAD.top - PAD.bottom;
  const label = (iso: string) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString(lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB", { day: "numeric", month: "short" });
  const ticks = data.length ? [0, Math.floor((data.length - 1) / 2), data.length - 1] : [];

  return (
    <div dir="ltr">
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={t("sel.daily")}>
      <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} className="stroke-line" />
      {data.map((d, i) => {
        const h = (d.revenue / max) * innerH;
        const x = PAD.left + i * step + (step - bar) / 2;
        return (
          <rect key={d.day} x={x} y={H - PAD.bottom - h} width={bar} height={Math.max(h, d.revenue > 0 ? 2 : 0)} rx={2} className="fill-accent">
            <title>{`${label(d.day)}: ${formatPrice(d.revenue, lang)} · ${d.orders}`}</title>
          </rect>
        );
      })}
      {ticks.map((i) => (
        <text key={i} x={PAD.left + i * step + step / 2} y={H - 6} textAnchor="middle" className="fill-ink-soft text-[11px]">
          {label(data[i].day)}
        </text>
      ))}
    </svg>
    </div>
  );
}
