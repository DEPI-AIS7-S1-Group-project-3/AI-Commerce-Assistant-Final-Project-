import { ApiError, http } from "./config";

// Backend /cart (login required). Only product_id + qty are used: product details,
// availability and totals come from the catalog, exactly like the local cart.
export type ApiCart = {
  items: { product_id: number; qty: number; available: boolean }[];
  subtotal_egp: string;
};

const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
const body = (data: unknown) => JSON.stringify(data);

export const getCart = (token: string) => http<ApiCart>("/cart", { headers: auth(token) });

export const addItem = (token: string, product_id: number, qty: number) =>
  http<ApiCart>("/cart/items", { method: "POST", headers: auth(token), body: body({ product_id, qty }) });

export const setItemQty = (token: string, product_id: number, qty: number) =>
  http<ApiCart>(`/cart/items/${product_id}`, { method: "PUT", headers: auth(token), body: body({ qty }) });

export const removeItem = (token: string, product_id: number) =>
  http<ApiCart>(`/cart/items/${product_id}`, { method: "DELETE", headers: auth(token) });

export const clearCart = (token: string) => http<ApiCart>("/cart", { method: "DELETE", headers: auth(token) });

/** For insufficient_stock errors: how many the backend says are available. */
export function availableFrom(e: unknown): number | null {
  if (e instanceof ApiError && e.code === "insufficient_stock") {
    const d = e.details as { available?: number } | undefined;
    return typeof d?.available === "number" ? d.available : null;
  }
  return null;
}
