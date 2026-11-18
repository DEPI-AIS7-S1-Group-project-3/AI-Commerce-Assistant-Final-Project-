import type { ProductReviews } from "@/types";
import { USE_MOCK, delay, http } from "./config";

type ApiProductReviews = Omit<ProductReviews, "rating_avg"> & { rating_avg: string | number | null };

const EMPTY_DIST = { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 } as const;

// Mock mode has no review data: the page shows its "no reviews yet" state.
export async function getProductReviews(productId: number, limit = 10): Promise<ProductReviews> {
  if (USE_MOCK) {
    await delay(150);
    return { product_id: productId, rating_avg: null, rating_count: 0, distribution: { ...EMPTY_DIST }, total: 0, reviews: [] };
  }
  const r = await http<ApiProductReviews>(`/products/${productId}/reviews?limit=${limit}`);
  return { ...r, rating_avg: r.rating_avg === null ? null : Number(r.rating_avg) };
}
