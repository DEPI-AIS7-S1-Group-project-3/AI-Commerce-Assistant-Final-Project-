import type { Brand, Category, Product, ProductQuery } from "@/types";
import { normalizeArabic } from "@/lib/arabic";
import { brands as mockBrands, categories as mockCategories } from "@/lib/mock/catalog";
import { mockProducts } from "@/lib/mock/products";
import { API_URL, ApiError, USE_MOCK, delay, http } from "./config";

// ---- real API -> frontend types ----
// The backend sends Decimal fields (prices, ratings) as exact strings like "9999.00",
// and image URLs as paths on the backend (/static/...). Convert both here, in one place.
type Dec = string | number;
type ApiProduct = Omit<Product, "price_egp" | "old_price_egp" | "rating_avg" | "seller"> & {
  price_egp: Dec;
  old_price_egp: Dec | null;
  rating_avg: Dec | null;
  seller: Omit<Product["seller"], "rating"> & { rating: Dec | null };
};

const toNum = (v: Dec | null): number | null => (v === null ? null : Number(v));
const absUrl = (url: string) => (url.startsWith("/") ? `${API_URL}${url}` : url);

function fromApi(p: ApiProduct): Product {
  return {
    ...p,
    price_egp: Number(p.price_egp),
    old_price_egp: toNum(p.old_price_egp),
    rating_avg: toNum(p.rating_avg),
    seller: { ...p.seller, rating: toNum(p.seller.rating) },
    images: p.images.map((i) => ({ ...i, url: absUrl(i.url) })),
  };
}

// Real endpoints: GET /products, /products/{id}, /categories, /brands (backend feat/catalog-listing).
// With VITE_USE_MOCK=true the mock data below is used instead. This file is the ONLY place
// that knows the difference.

function applyQuery(items: Product[], query: ProductQuery): Product[] {
  let out = items.filter((p) => p.is_active);

  if (query.q) {
    const needle = normalizeArabic(query.q);
    out = out.filter((p) =>
      normalizeArabic(`${p.title_ar} ${p.brand.name} ${p.brand.name_ar ?? ""} ${p.category.name_ar}`).includes(needle),
    );
  }
  if (query.category) out = out.filter((p) => p.category.slug === query.category);
  if (query.brand) out = out.filter((p) => p.brand.slug === query.brand);
  if (query.min_price != null) out = out.filter((p) => p.price_egp >= query.min_price!);
  if (query.max_price != null) out = out.filter((p) => p.price_egp <= query.max_price!);
  if (query.in_stock) out = out.filter((p) => p.stock_qty > 0);

  const sorted = [...out];
  switch (query.sort) {
    case "price_asc":
      sorted.sort((a, b) => a.price_egp - b.price_egp);
      break;
    case "price_desc":
      sorted.sort((a, b) => b.price_egp - a.price_egp);
      break;
    case "rating":
      sorted.sort((a, b) => (b.rating_avg ?? 0) - (a.rating_avg ?? 0));
      break;
    default:
      sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  return sorted;
}

export async function listProducts(query: ProductQuery = {}): Promise<Product[]> {
  if (USE_MOCK) {
    await delay();
    return applyQuery(mockProducts, query);
  }
  const params = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== "" && v !== false) params.set(k, String(v));
  });
  const items = await http<ApiProduct[]>(`/products?${params.toString()}`);
  return items.map(fromApi);
}

export async function getProduct(id: number): Promise<Product | null> {
  if (USE_MOCK) {
    await delay(200);
    return mockProducts.find((p) => p.id === id) ?? null;
  }
  try {
    return fromApi(await http<ApiProduct>(`/products/${id}`));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null; // same as the mock: not found = null
    throw e;
  }
}

export async function listCategories(): Promise<Category[]> {
  if (USE_MOCK) {
    await delay(100);
    return mockCategories;
  }
  return http<Category[]>(`/categories`);
}

export async function listBrands(): Promise<Brand[]> {
  if (USE_MOCK) {
    await delay(100);
    return mockBrands;
  }
  return http<Brand[]>(`/brands`);
}

export { API_URL };
