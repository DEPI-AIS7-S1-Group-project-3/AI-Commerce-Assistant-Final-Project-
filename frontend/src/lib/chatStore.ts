import type { Reply } from "@/lib/assistantScript";

export type StoredMsg =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; reply: Reply };

export type Chat = { id: string; title: string; updatedAt: number; messages: StoredMsg[] };

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