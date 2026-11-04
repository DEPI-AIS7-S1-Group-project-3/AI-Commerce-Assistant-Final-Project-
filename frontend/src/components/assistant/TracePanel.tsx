import { useI18n } from "@/lib/i18n";

export default function TracePanel({ steps }: { steps: { name: string; ms: number }[] }) {
  const { t } = useI18n();
  const total = steps.reduce((sum, s) => sum + s.ms, 0);
  return (
    <div dir="ltr" className="mt-3 rounded-ctl border border-line bg-black p-4 font-mono text-xs text-neon">
      <p className="mb-2 text-ink-soft">{t("as.trace.note")}</p>
      <ul className="space-y-1">
        {steps.map((s) => (
          <li key={s.name} className="flex justify-between gap-6">
            <span>{s.name}</span>
            <span className="text-ink-soft">{s.ms} ms</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 flex justify-between border-t border-line pt-2">
        <span>total</span>
        <span>{total} ms</span>
      </p>
    </div>
  );
}