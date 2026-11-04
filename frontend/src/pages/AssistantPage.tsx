import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronDown, Plus, Sparkles, Trash2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useProducts } from "@/hooks/useProducts";
import { useChats } from "@/hooks/useChats";
import { newId } from "@/lib/chatStore";
import { scriptedReply, suggestions, traceFor } from "@/lib/assistantScript";
import RecommendationTable from "@/components/assistant/RecommendationTable";
import TracePanel from "@/components/assistant/TracePanel";

export default function AssistantPage() {
  const { t, lang } = useI18n();
  const { data } = useProducts({});
  const all = data ?? [];
  const { chats, active, activeId, setActiveId, addMessage, remove } = useChats();
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const endRef = useRef<HTMLDivElement>(null);

  const messages = active?.messages ?? [];

  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pending]);

  const send = (query: string, display?: string) => {
    const text = query.trim();
    if (!text || pending) return;
    const chatId = activeId ?? newId();
    if (!activeId) setActiveId(chatId);
    addMessage(chatId, { id: newId(), role: "user", text: display ?? text });
    setInput("");
    setPending(true);
    timer.current = window.setTimeout(() => {
      addMessage(chatId, { id: newId(), role: "assistant", reply: scriptedReply(text, all) });
      setPending(false);
    }, 900);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  return (
    <div className="grid gap-8 md:grid-cols-[240px_1fr]">
      <aside className="space-y-3" aria-label={t("as.history")}>
        <button type="button" className="btn-primary w-full" onClick={() => setActiveId(null)}>
          <Plus className="h-4 w-4" aria-hidden />
          {t("as.new")}
        </button>
        <h2 className="pt-2 text-base">{t("as.history")}</h2>
        {chats.length === 0 ? (
          <p className="text-sm text-ink-soft">{t("as.nohistory")}</p>
        ) : (
          <ul className="space-y-1">
            {chats.map((c) => (
              <li key={c.id} className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setActiveId(c.id)}
                  className={`flex-1 truncate rounded-ctl px-3 py-2 text-start text-sm ${
                    c.id === activeId ? "bg-surface text-neon" : "text-ink-soft hover:bg-surface"
                  }`}
                >
                  {c.title}
                </button>
                <button type="button" className="p-2 text-ink-soft hover:text-danger" onClick={() => remove(c.id)} aria-label={t("as.delete")}>
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="flex min-w-0 flex-col gap-6">
        <header className="space-y-2 border-b border-line pb-5">
          <h1 className="flex items-center gap-3 text-4xl">
            <Sparkles className="h-8 w-8 text-neon" aria-hidden />
            {t("assistant.title")}
          </h1>
          <p className="text-ink-soft">{t("as.sub")}</p>
        </header>

        <div className="space-y-6" aria-live="polite">
          {messages.map((m, idx) => {
            if (m.role === "user") {
              return (
                <div key={m.id} className="flex flex-col items-end gap-1">
                  <span className="text-xs text-ink-soft">{t("as.you")}</span>
                  <p className="max-w-[85%] rounded-ctl bg-green px-4 py-2 text-white">{m.text}</p>
                </div>
              );
            }
            const recs = m.reply.productIds
              .map((id) => all.find((p) => p.id === id))
              .filter((p): p is NonNullable<typeof p> => Boolean(p));
            const isLast = idx === messages.length - 1;
            return (
              <div key={m.id} className="border-s-2 border-neon ps-4">
                <span className="text-xs text-ink-soft">{t("as.name")}</span>
                <p className="mt-1">{m.reply.text[lang]}</p>
                {recs.length > 0 && <RecommendationTable products={recs} reasons={m.reply.reasons} />}
                <p className="mt-3 text-xs text-ink-soft">
                  {t("as.conf")}: {m.reply.confident ? t("as.conf.high") : t("as.conf.low")}
                </p>
                {isLast && m.reply.followups.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <p className="text-xs text-ink-soft">{t("as.next")}</p>
                    <div className="flex flex-wrap gap-2">
                      {m.reply.followups.map((f) => (
                        <button key={f.query} type="button" className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => send(f.query, f.label[lang])}>
                          {f.label[lang]}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {pending && <p className="border-s-2 border-neon ps-4 text-sm text-ink-soft">{t("as.checking")}...</p>}
          <div ref={endRef} />
        </div>

        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-ink-soft">{t("as.try")}</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button key={s.query} type="button" className="btn-ghost !px-3 !py-2 text-sm" onClick={() => send(s.query, s.label[lang])}>
                  {s.label[lang]}
                </button>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="flex gap-2 border-t border-line pt-4">
          <input className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("as.placeholder")} aria-label={t("as.placeholder")} />
          <button type="submit" className="btn-primary !px-4" disabled={pending} aria-label={t("as.send")}>
            <ArrowUp className="h-5 w-5" aria-hidden />
          </button>
        </form>

        {lastAssistant && lastAssistant.role === "assistant" && (
          <div>
            <button type="button" className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-neon" onClick={() => setShowTrace((v) => !v)}>
              <ChevronDown className={`h-4 w-4 transition-transform ${showTrace ? "rotate-180" : ""}`} aria-hidden />
              {t("as.trace")}
            </button>
            {showTrace && <TracePanel steps={traceFor(lastAssistant.reply)} />}
          </div>
        )}
      </section>
    </div>
  );
}