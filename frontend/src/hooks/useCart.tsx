import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CartLine } from "@/types";
import { ApiError, USE_MOCK } from "@/api/config";
import * as api from "@/api/cart";
import { getToken, useAuth } from "@/hooks/useAuth";

// Two modes behind one interface:
// - local:  guests, and everyone in mock mode. Context + localStorage.
// - server: logged-in user with the real backend. Every change goes to /cart.
// On login, the guest's local lines are merged into the server cart once, then cleared.

export type CartError = "stock" | "unavailable" | "network";

type Ctx = {
  lines: CartLine[];
  count: number;
  error: CartError | null;
  clearError: () => void;
  /** Resolves true on success, false on failure (see `error`). Never throws. */
  add: (productId: number, qty?: number) => Promise<boolean>;
  setQty: (productId: number, qty: number) => void;
  remove: (productId: number) => void;
  clear: () => void;
};

const CartContext = createContext<Ctx | null>(null);
const KEY = "dalil.cart.v1";
const clamp = (n: number) => Math.max(1, Math.min(100, Math.floor(n)));
const toLines = (c: api.ApiCart): CartLine[] => c.items.map((i) => ({ product_id: i.product_id, qty: i.qty }));

function load(): CartLine[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((l) => typeof l?.product_id === "number" && typeof l?.qty === "number");
  } catch {
    return [];
  }
}

function save(lines: CartLine[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(lines));
  } catch {
    /* ignore */
  }
}

function toError(e: unknown): CartError {
  if (e instanceof ApiError) {
    if (e.code === "insufficient_stock") return "stock";
    if (e.code === "product_not_found" || e.code === "cart_item_not_found") return "unavailable";
  }
  return "network";
}

/** Add guest lines to the server cart. Quantities add up; capped at stock; gone products skipped. */
async function mergeLines(token: string, lines: CartLine[]): Promise<void> {
  let cart = await api.getCart(token);
  for (const line of lines) {
    try {
      cart = await api.addItem(token, line.product_id, line.qty);
    } catch (e) {
      const available = api.availableFrom(e);
      const have = cart.items.find((i) => i.product_id === line.product_id)?.qty ?? 0;
      if (available !== null && available - have > 0) {
        cart = await api.addItem(token, line.product_id, available - have);
      }
    }
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const serverMode = !USE_MOCK && user !== null;

  const [local, setLocal] = useState<CartLine[]>(load);
  const [server, setServer] = useState<CartLine[]>([]);
  const [error, setError] = useState<CartError | null>(null);
  const localRef = useRef(local);
  localRef.current = local;
  const mergedFor = useRef<number | null>(null); // user id whose login merge already ran

  useEffect(() => save(local), [local]);

  const handle = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) logout(); // expired login
      setError(toError(e));
    },
    [logout],
  );

  // Login: merge the guest cart into the server cart (once per user), then load it.
  // The merge promise is kept in a ref so a second effect run (React dev mode runs
  // effects twice) waits for the same merge instead of starting another one.
  const mergeRef = useRef<Promise<void>>(Promise.resolve());
  useEffect(() => {
    if (!serverMode || !user) {
      setServer([]);
      mergedFor.current = null;
      return;
    }
    const token = getToken();
    if (!token) return;
    if (mergedFor.current !== user.id) {
      mergedFor.current = user.id;
      const toMerge = localRef.current;
      if (toMerge.length) {
        setLocal([]);
        save([]);
        mergeRef.current = mergeLines(token, toMerge);
      }
    }
    let cancelled = false;
    (async () => {
      try {
        await mergeRef.current;
        const cart = await api.getCart(token);
        if (!cancelled) setServer(toLines(cart));
      } catch (e) {
        if (!cancelled) handle(e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [serverMode, user, handle]);

  const run = useCallback(
    async (call: (token: string) => Promise<api.ApiCart>): Promise<boolean> => {
      const token = getToken();
      if (!token) return false;
      try {
        setServer(toLines(await call(token)));
        setError(null);
        return true;
      } catch (e) {
        handle(e);
        return false;
      }
    },
    [handle],
  );

  const add = useCallback(
    async (productId: number, qty = 1) => {
      if (serverMode) return run((tk) => api.addItem(tk, productId, clamp(qty)));
      setLocal((prev) => {
        const found = prev.find((l) => l.product_id === productId);
        if (found) return prev.map((l) => (l.product_id === productId ? { ...l, qty: clamp(l.qty + qty) } : l));
        return [...prev, { product_id: productId, qty: clamp(qty) }];
      });
      return true;
    },
    [serverMode, run],
  );

  const setQty = useCallback(
    (productId: number, qty: number) => {
      if (serverMode) void run((tk) => api.setItemQty(tk, productId, clamp(qty)));
      else setLocal((prev) => prev.map((l) => (l.product_id === productId ? { ...l, qty: clamp(qty) } : l)));
    },
    [serverMode, run],
  );

  const remove = useCallback(
    (productId: number) => {
      if (serverMode) void run((tk) => api.removeItem(tk, productId));
      else setLocal((prev) => prev.filter((l) => l.product_id !== productId));
    },
    [serverMode, run],
  );

  const clear = useCallback(() => {
    if (serverMode) void run((tk) => api.clearCart(tk));
    else setLocal([]);
  }, [serverMode, run]);

  const clearError = useCallback(() => setError(null), []);
  const lines = serverMode ? server : local;
  const count = useMemo(() => lines.reduce((sum, l) => sum + l.qty, 0), [lines]);
  const value = useMemo(
    () => ({ lines, count, error, clearError, add, setQty, remove, clear }),
    [lines, count, error, clearError, add, setQty, remove, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
