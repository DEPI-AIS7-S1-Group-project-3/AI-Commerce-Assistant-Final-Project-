import { useI18n } from "@/lib/i18n";

export default function TracePanel({ trace }: { trace: unknown }) {
  const { t } = useI18n();

  if (!trace) return null;

  // If array of step objects { name, ms }
  if (Array.isArray(trace) && trace.every((s) => s && typeof s === "object" && "name" in s)) {
    const steps = trace as { name: string; ms: number }[];
    const total = steps.reduce((sum, s) => sum + (Number(s.ms) || 0), 0);
    return (
      <div dir="ltr" data-theme="dark" className="mt-3 rounded-ctl border border-line bg-black p-4 font-mono text-xs text-neon">
        <p className="mb-2 text-ink-soft">{t("as.trace")}</p>
        <ul className="space-y-1">
          {steps.map((s, i) => (
            <li key={i} className="flex justify-between gap-6">
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

  return (
    <div dir="ltr" data-theme="dark" className="mt-3 rounded-ctl border border-line bg-black p-4 font-mono text-xs text-neon overflow-x-auto">
      <p className="mb-2 text-ink-soft">{t("as.trace")}</p>
      <pre className="whitespace-pre-wrap">{JSON.stringify(trace, null, 2)}</pre>
    </div>
  );
}