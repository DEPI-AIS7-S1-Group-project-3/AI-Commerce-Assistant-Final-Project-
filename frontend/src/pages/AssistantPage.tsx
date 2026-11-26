import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowUp,
  ChevronDown,
  HelpCircle,
  LogIn,
  MessagesSquare,
  PackageCheck,
  Plus,
  RefreshCw,
  ShoppingBag,
  Sparkles,
  Store,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useI18n, type TKey } from "@/lib/i18n";
import { useAuth } from "@/hooks/useAuth";
import { useChats } from "@/hooks/useChats";
import { newId } from "@/lib/chatStore";
import { suggestions } from "@/lib/assistantScript";
import { sendMessage, type AgentName } from "@/api/assistant";
import { ApiError } from "@/api/config";
import MiniMarkdown from "@/components/MiniMarkdown";
import TracePanel from "@/components/assistant/TracePanel";
import AssistantProductCards from "@/components/assistant/AssistantProductCards";

function getAgentMeta(agent: AgentName, t: (k: TKey) => string): {
  icon: LucideIcon;
  label: string;
  badgeClass: string;
} {
  switch (agent) {
    case "shopping":
      return {
        icon: ShoppingBag,
        label: t("as.agent.shopping"),
        badgeClass: "text-accent bg-accent/10 border-accent/20",
      };
    case "support":
      return {
        icon: HelpCircle,
        label: t("as.agent.support"),
        badgeClass: "text-amber-600 bg-amber-500/10 border-amber-500/20",
      };
    case "order_actions":
      return {
        icon: PackageCheck,
        label: t("as.agent.order_actions"),
        badgeClass: "text-blue-600 bg-blue-500/10 border-blue-500/20",
      };
    case "seller":
      return {
        icon: Store,
        label: t("as.agent.seller"),
        badgeClass: "text-purple-600 bg-purple-500/10 border-purple-500/20",
      };
    default:
      return {
        icon: Sparkles,
        label: t("as.name"),
        badgeClass: "text-accent bg-surface border-line",
      };
  }
}

interface ChatError {
  status: number;
  code: string;
  message: string;
  lastFailedText?: string;
}

export default function AssistantPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const {
    chats,
    activeId,
    active,
    setActiveId,
    addMessage,
    setBackendConvoId,
    remove,
    clearAllBackendIds,
  } = useChats();

  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [openTrace, setOpenTrace] = useState<Set<string>>(new Set());

  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const prevUserId = useRef<number | undefined>(user?.id);

  const messages = active?.messages ?? [];

  // Reset conversation context on login or logout as required by the backend contract
  useEffect(() => {
    if (prevUserId.current !== user?.id) {
      prevUserId.current = user?.id;
      setActiveId(null);
      clearAllBackendIds();
    }
  }, [user?.id, setActiveId, clearAllBackendIds]);

  // Auto-scroll the message list only (never the whole window)
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, pending, activeId, error]);

  const send = async (query: string, display?: string) => {
    const text = query.trim();
    if (!text || text.length > 2000 || pending) return;

    setError(null);
    const chatId = activeId ?? newId();
    if (!activeId) setActiveId(chatId);

    // Append user message immediately
    addMessage(chatId, { id: newId(), role: "user", text: display ?? text });
    setInput("");
    setPending(true);

    const backendConvo = active?.id === chatId ? active?.backendConvoId : null;

    try {
      const res = await sendMessage(text, backendConvo);
      setBackendConvoId(chatId, res.conversation_id);
      addMessage(chatId, {
        id: newId(),
        role: "assistant",
        reply: {
          text: res.reply,
          agent: res.agent,
          products: res.products ?? [],
          needs_confirmation: res.needs_confirmation ?? null,
          trace: res.trace ?? null,
        },
      });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          // Stored conversation_id is invalid or belongs to another user
          setBackendConvoId(chatId, "");
          setError({
            status: 404,
            code: err.code,
            message: t("as.err.notfound"),
            lastFailedText: text,
          });
        } else if (err.status === 401) {
          setError({
            status: 401,
            code: err.code,
            message: t("as.err.unauthorized"),
          });
        } else if (err.status === 503) {
          setError({
            status: 503,
            code: err.code,
            message: t("as.err.unavailable"),
            lastFailedText: text,
          });
        } else {
          setError({
            status: err.status,
            code: err.code,
            message: err.message || t("as.err.generic"),
            lastFailedText: text,
          });
        }
      } else {
        setError({
          status: 500,
          code: "error",
          message: t("as.err.generic"),
          lastFailedText: text,
        });
      }
    } finally {
      setPending(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
    inputRef.current?.focus();
  };

  const pick = (id: string | null) => {
    setActiveId(id);
    setError(null);
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
              <button
                type="button"
                className="p-2 text-ink-soft hover:text-danger"
                onClick={() => remove(c.id)}
                aria-label={t("as.delete")}
              >
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
      <aside
        className="hidden w-60 shrink-0 flex-col gap-3 overflow-y-auto md:flex"
        aria-label={t("as.history")}
      >
        {history}
      </aside>

      {/* phone history drawer */}
      {drawer && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={t("as.history")}
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label={t("products.close")}
            onClick={() => setDrawer(false)}
          />
          <div className="absolute inset-y-0 start-0 flex w-72 max-w-[85%] flex-col gap-3 overflow-y-auto bg-paper p-4">
            <button
              type="button"
              className="ms-auto p-1 text-ink-soft"
              onClick={() => setDrawer(false)}
              aria-label={t("products.close")}
            >
              <X className="h-5 w-5" aria-hidden />
            </button>
            {history}
          </div>
        </div>
      )}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center gap-3 border-b border-line pb-3">
          <button
            type="button"
            className="btn-ghost !p-2 md:hidden"
            onClick={() => setDrawer(true)}
            aria-label={t("as.history")}
          >
            <MessagesSquare className="h-5 w-5" aria-hidden />
          </button>
          <h1 className="flex min-w-0 items-center gap-2 text-2xl sm:text-3xl">
            <Sparkles className="h-6 w-6 shrink-0 text-accent" aria-hidden />
            <span className="truncate">{active?.title ?? t("assistant.title")}</span>
          </h1>
          {activeId && (
            <button
              type="button"
              className="btn-ghost ms-auto !p-2"
              onClick={() => pick(null)}
              aria-label={t("as.new")}
              title={t("as.new")}
            >
              <Plus className="h-5 w-5" aria-hidden />
            </button>
          )}
        </header>

        <div
          ref={listRef}
          className="min-h-0 flex-1 space-y-6 overflow-y-auto py-4"
          aria-live="polite"
        >
          {messages.length === 0 && (
            <div className="space-y-4 py-6">
              <p className="text-ink-soft">{t("as.sub")}</p>
              <p className="text-sm text-ink-soft">{t("as.try")}</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s.query}
                    type="button"
                    className="btn-ghost !px-3 !py-2 text-sm"
                    onClick={() => send(s.query, s.label[lang])}
                  >
                    {s.label[lang]}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, idx) => {
            if (m.role === "user") {
              const isArabic = /[\u0600-\u06FF]/.test(m.text);
              return (
                <div key={m.id} className="flex flex-col items-end gap-1">
                  <span className="text-xs text-ink-soft">{t("as.you")}</span>
                  <p
                    dir={isArabic ? "rtl" : "ltr"}
                    className="max-w-[85%] rounded-ctl bg-green px-4 py-2 text-white"
                  >
                    {m.text}
                  </p>
                </div>
              );
            }

            const isLast = idx === messages.length - 1;
            const traceOpen = openTrace.has(m.id);
            const agentMeta = getAgentMeta(m.reply.agent, t);
            const AgentIcon = agentMeta.icon;
            const isArabicReply = /[\u0600-\u06FF]/.test(m.reply.text);

            return (
              <div key={m.id} className="border-s-2 border-accent ps-4">
                {/* Agent badge */}
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${agentMeta.badgeClass}`}
                  >
                    <AgentIcon className="h-3.5 w-3.5" aria-hidden />
                    {agentMeta.label}
                  </span>
                </div>

                {/* Markdown text reply */}
                <div dir={isArabicReply ? "rtl" : "ltr"} className="mt-2 text-start">
                  <MiniMarkdown md={m.reply.text} />
                </div>

                {/* Products cards */}
                {m.reply.products && m.reply.products.length > 0 && (
                  <AssistantProductCards products={m.reply.products} />
                )}

                {/* Confirmation flow (Cancel & Return) */}
                {isLast && m.reply.needs_confirmation && (
                  <div
                    className={
                      m.reply.needs_confirmation.question.trim() !== m.reply.text.trim()
                        ? "mt-4 rounded-ctl border border-line bg-surface p-3"
                        : "mt-3"
                    }
                  >
                    {/* The backend reply already holds this question: show it once */}
                    {m.reply.needs_confirmation.question.trim() !== m.reply.text.trim() && (
                      <p className="text-sm font-medium">{m.reply.needs_confirmation.question}</p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-primary !px-5 !py-2 text-sm font-semibold"
                        disabled={pending}
                        onClick={() => send("أيوه")}
                      >
                        {t("as.confirm.yes")}
                      </button>
                      <button
                        type="button"
                        className="btn-ghost !px-5 !py-2 text-sm font-semibold border border-line"
                        disabled={pending}
                        onClick={() => send("لأ")}
                      >
                        {t("as.confirm.no")}
                      </button>
                    </div>
                  </div>
                )}

                {/* Visitor asks to cancel/return -> offer login button if support answered */}
                {m.reply.agent === "support" && !user && (
                  <div className="mt-3 flex items-center justify-between rounded-ctl border border-line bg-surface p-3 text-sm">
                    <span className="text-ink-soft">{t("as.signin.prompt")}</span>
                    <Link to="/login" className="btn-primary !px-3 !py-1 text-xs">
                      <LogIn className="h-3.5 w-3.5" aria-hidden />
                      {t("as.signin.btn")}
                    </Link>
                  </div>
                )}

                {/* Debug Trace (if backend returned one with ASSISTANT_DEBUG_TRACE=true) */}
                {m.reply.trace !== null && (
                  <div className="mt-3">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-accent"
                      aria-expanded={traceOpen}
                      onClick={() => toggleTrace(m.id)}
                    >
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition-transform ${traceOpen ? "rotate-180" : ""}`}
                        aria-hidden
                      />
                      {t("as.trace")}
                    </button>
                    {traceOpen && <TracePanel trace={m.reply.trace} />}
                  </div>
                )}
              </div>
            );
          })}

          {/* Typing indicator while assistant is thinking (tool calls take 2-8s) */}
          {pending && (
            <div className="border-s-2 border-accent ps-4">
              <div className="flex items-center gap-2 text-sm text-ink-soft">
                <span className="flex space-x-1 rtl:space-x-reverse">
                  <span className="h-2 w-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="h-2 w-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="h-2 w-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: "300ms" }} />
                </span>
                <span>{t("as.checking")}...</span>
              </div>
            </div>
          )}

          {/* Error notification with retry option */}
          {error && (
            <div className="rounded-ctl border border-danger/30 bg-danger/10 p-3 text-sm text-danger flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />
                <span>{error.message}</span>
              </div>
              {error.lastFailedText && error.status !== 401 && (
                <button
                  type="button"
                  className="btn-primary !px-3 !py-1 text-xs"
                  onClick={() => send(error.lastFailedText!)}
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                  {t("as.err.retry")}
                </button>
              )}
              {error.status === 401 && (
                <Link to="/login" className="btn-primary !px-3 !py-1 text-xs">
                  {t("as.signin.btn")}
                </Link>
              )}
            </div>
          )}
        </div>

        <form onSubmit={onSubmit} className="flex shrink-0 flex-col gap-1 border-t border-line pt-3">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              className="input flex-1"
              value={input}
              maxLength={2000}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("as.placeholder")}
              aria-label={t("as.placeholder")}
            />
            <button
              type="submit"
              className="btn-primary !px-4"
              disabled={pending || !input.trim() || input.length > 2000}
              aria-label={t("as.send")}
            >
              <ArrowUp className="h-5 w-5" aria-hidden />
            </button>
          </div>
          {input.length > 1800 && (
            <span className="text-end text-xs text-ink-soft">
              {input.length} / 2000
            </span>
          )}
        </form>
      </section>
    </div>
  );
}
