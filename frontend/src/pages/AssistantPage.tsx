import { type FormEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronDown, MessagesSquare, Plus, Sparkles, Trash2, X } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useProducts } from "@/hooks/useProducts";
import { useChats } from "@/hooks/useChats";
import { newId } from "@/lib/chatStore";
import { scriptedReply, suggestions, traceFor } from "@/lib/assistantScript";
import RecommendationTable from "@/components/assistant/RecommendationTable";
import TracePanel from "@/components/assistant/TracePanel";

// Chat-app layout: the page fills the screen (see Layout FULL_SCREEN), only the message list
// scrolls, and the input stays pinned at the bottom. History is a side panel on desktop and a
// drawer on phones.
export default function AssistantPage() {
  const { t, lang } = useI18n();
  const { data } = useProducts({});
  const all = data ?? [];
  const { chats, activeId, active, setActiveId, addMessage, remove } = useChats();
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [openTrace, setOpenTrace] = useState<Set<string>>(new Set());
  const timer = useRef<number | undefined>(undefined);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const messages = active?.messages ?? [];

  useEffect(() => () => window.clearTimeout(timer.current), []);
  // Auto-scroll the MESSAGE LIST only (never the window).
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, pending, activeId]);

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
    inputRef.current?.focus();
  };

  const pick = (id: string | null) => {
    setActiveId(id);
    setDrawer(false);
  };

  const toggleTrace = (id: string) =>
    setOpenTrace((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const history = (
    <>
      <button type="button" className="btn-primary w-full" onClick={() => pick(null)}>
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
                onClick={() => pick(c.id)}
                className={`min-w-0 flex-1 truncate rounded-ctl px-3 py-2 text-start text-sm ${
                  c.id === activeId ? "bg-surface text-accent" : "text-ink-soft hover:bg-surface"
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
    </>
  );

  return (
    <div className="flex min-h-0 w-full gap-6">
      {/* desktop history */}
      <aside className="hidden w-60 shrink-0 flex-col gap-3 overflow-y-auto md:flex" aria-label={t("as.history")}>
        {history}
      </aside>

      {/* phone history drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label={t("as.history")}>
          <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("products.close")} onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 start-0 flex w-72 max-w-[85%] flex-col gap-3 overflow-y-auto bg-paper p-4">
            <button type="button" className="ms-auto p-1 text-ink-soft" onClick={() => setDrawer(false)} aria-label={t("products.close")}>
              <X className="h-5 w-5" aria-hidden />
            </button>
            {history}
          </div>
        </div>
      )}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center gap-3 border-b border-line pb-3">
          <button type="button" className="btn-ghost !p-2 md:hidden" onClick={() => setDrawer(true)} aria-label={t("as.history")}>
            <MessagesSquare className="h-5 w-5" aria-hidden />
          </button>
          <h1 className="flex min-w-0 items-center gap-2 text-2xl sm:text-3xl">
            <Sparkles className="h-6 w-6 shrink-0 text-accent" aria-hidden />
            <span className="truncate">{active?.title ?? t("assistant.title")}</span>
          </h1>
          {activeId && (
            <button type="button" className="btn-ghost ms-auto !p-2" onClick={() => pick(null)} aria-label={t("as.new")} title={t("as.new")}>
              <Plus className="h-5 w-5" aria-hidden />
            </button>
          )}
        </header>

        <div ref={listRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto py-4" aria-live="polite">
          {messages.length === 0 && (
            <div className="space-y-4 py-6">
              <p className="text-ink-soft">{t("as.sub")}</p>
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
            const traceOpen = openTrace.has(m.id);
            return (
              <div key={m.id} className="border-s-2 border-accent ps-4">
                <span className="text-xs text-ink-soft">{t("as.name")}</span>
                <p className="mt-1">{m.reply.text[lang]}</p>
                {recs.length > 0 && <RecommendationTable products={recs} reasons={m.reply.reasons} />}
                <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-ink-soft">
                  <span>
                    {t("as.conf")}: {m.reply.confident ? t("as.conf.high") : t("as.conf.low")}
                  </span>
                  <button type="button" className="inline-flex items-center gap-1 hover:text-accent" aria-expanded={traceOpen} onClick={() => toggleTrace(m.id)}>
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform ${traceOpen ? "rotate-180" : ""}`} aria-hidden />
                    {t("as.trace")}
                  </button>
                </div>
                {traceOpen && <TracePanel steps={traceFor(m.reply)} />}
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
          {pending && <p className="border-s-2 border-accent ps-4 text-sm text-ink-soft">{t("as.checking")}...</p>}
        </div>

        <form onSubmit={onSubmit} className="flex shrink-0 gap-2 border-t border-line pt-3">
          <input
            ref={inputRef}
            className="input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("as.placeholder")}
            aria-label={t("as.placeholder")}
          />
          <button type="submit" className="btn-primary !px-4" disabled={pending} aria-label={t("as.send")}>
            <ArrowUp className="h-5 w-5" aria-hidden />
          </button>
        </form>
      </section>
    </div>
  );
}
