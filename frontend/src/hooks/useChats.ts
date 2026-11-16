import { useCallback, useEffect, useState } from "react";
import { loadChats, saveChats, type Chat, type StoredMsg } from "@/lib/chatStore";

export function useChats() {
  const [chats, setChats] = useState<Chat[]>(loadChats);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    saveChats(chats);
  }, [chats]);

  const addMessage = useCallback((chatId: string, msg: StoredMsg) => {
    setChats((prev) => {
      const exists = prev.some((c) => c.id === chatId);
      if (!exists) {
        const title = msg.role === "user" ? msg.text.slice(0, 40) : "...";
        return [{ id: chatId, title, updatedAt: Date.now(), messages: [msg] }, ...prev];
      }
      return prev
        .map((c) => (c.id === chatId ? { ...c, updatedAt: Date.now(), messages: [...c.messages, msg] } : c))
        .sort((a, b) => b.updatedAt - a.updatedAt);
    });
  }, []);

  const remove = useCallback((chatId: string) => {
    setChats((prev) => prev.filter((c) => c.id !== chatId));
    setActiveId((cur) => (cur === chatId ? null : cur));
  }, []);

  const active = chats.find((c) => c.id === activeId) ?? null;
  return { chats, active, activeId, setActiveId, addMessage, remove };
}