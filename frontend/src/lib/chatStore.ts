import type { AgentName, ProductCard } from "@/api/assistant";

/** What the backend really returns, stored per assistant message. */
export interface AssistantReply {
  text: string;
  agent: AgentName;
  products: ProductCard[];
  needs_confirmation: { question: string } | null;
  trace: unknown | null;
}

export type StoredMsg =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; reply: AssistantReply };

export type Chat = {
  id: string;
  /** First user message, used as the sidebar title. */
  title: string;
  updatedAt: number;
  /** Backend conversation id (uuid) for follow-up messages. */
  backendConvoId: string | null;
  messages: StoredMsg[];
};

const KEY = "dalil.chats.v1";

export const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export function loadChats(): Chat[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveChats(chats: Chat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats));
  } catch {
    /* storage full or blocked: ignore */
  }
}