import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { CartLine } from "@/types";

type Ctx = {
  lines: CartLine[];
  count: number;
  add: (productId: number, qty?: number) => void;
  setQty: (productId: number, qty: number) => void;
  remove: (productId: number) => void;
  clear: () => void;
};

const CartContext = createContext<Ctx | null>(null);
const KEY = "dalil.cart.v1";
const clamp = (n: number) => Math.max(1, Math.min(100, Math.floor(n)));

function load(): CartLine[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((l) => typeof l?.product_id === "number" && typeof l?.qty === "number");
  } catch {
    return [];
  }
}

// Local cart (context + localStorage). To be replaced by the backend /cart endpoints after auth.
export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(lines));
    } catch {
      /* ignore */
    }
  }, [lines]);

  const add = useCallback((productId: number, qty = 1) => {
    setLines((prev) => {
      const found = prev.find((l) => l.product_id === productId);
      if (found) return prev.map((l) => (l.product_id === productId ? { ...l, qty: clamp(l.qty + qty) } : l));
      return [...prev, { product_id: productId, qty: clamp(qty) }];
    });
  }, []);

  const setQty = useCallback((productId: number, qty: number) => {
    setLines((prev) => prev.map((l) => (l.product_id === productId ? { ...l, qty: clamp(qty) } : l)));
  }, []);

  const remove = useCallback((productId: number) => {
    setLines((prev) => prev.filter((l) => l.product_id !== productId));
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const count = useMemo(() => lines.reduce((sum, l) => sum + l.qty, 0), [lines]);
  const value = useMemo(() => ({ lines, count, add, setQty, remove, clear }), [lines, count, add, setQty, remove, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}