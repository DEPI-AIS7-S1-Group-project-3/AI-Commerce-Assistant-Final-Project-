import { API_URL, ApiError } from "@/api/config";
import { getToken } from "@/hooks/useAuth";

// ── Types matching the real POST /assistant/chat contract ──────────────

export type AgentName = "shopping" | "support" | "order_actions" | "seller";

export interface ProductCard {
  id: number;
  title_ar: string;
  brand: string;
  category_slug: string;
  price_egp: string; // decimal string from server
  old_price_egp: string | null;
  rating_avg: string | null;
  rating_count: number;
  in_stock: boolean;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
  agent: AgentName;
  products: ProductCard[];
  needs_confirmation: { question: string } | null;
  trace: unknown | null;
}

// ── API call ───────────────────────────────────────────────────────────

export async function sendMessage(
  message: string,
  conversationId?: string | null,
): Promise<ChatResponse> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const body: Record<string, string> = { message };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 35000);

  try {
    const res = await fetch(`${API_URL}/assistant/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!res.ok) {
      let parsed: { code?: string; message?: string } = {};
      try {
        parsed = await res.json();
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(
        res.status,
        parsed.code ?? "unknown_error",
        parsed.message ?? res.statusText,
      );
    }

    return (await res.json()) as ChatResponse;
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(503, "assistant_unavailable", "Request timed out after 35 seconds");
    }
    throw new ApiError(500, "network_error", (err as Error)?.message ?? "Network error");
  } finally {
    clearTimeout(timeoutId);
  }
}
