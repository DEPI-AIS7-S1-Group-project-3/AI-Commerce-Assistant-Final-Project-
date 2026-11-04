import type { Brand, Category, Product, ProductQuery } from "@/types";
import { normalizeArabic } from "@/lib/arabic";
import { brands as mockBrands, categories as mockCategories } from "@/lib/mock/catalog";
import { mockProducts } from "@/lib/mock/products";
import { API_URL, USE_MOCK, delay, http } from "./config";

// NOTE: the backend has NO product/category endpoints yet (audit 2026-11-04).
// The real-API branches below follow a PROPOSED contract. Confirm with the backend owner
// before setting VITE_USE_MOCK=false. This file is the ONLY place that should change.

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
  return http<Product[]>(`/products?${params.toString()}`);
}

export async function getProduct(id: number): Promise<Product | null> {
  if (USE_MOCK) {
    await delay(200);
    return mockProducts.find((p) => p.id === id) ?? null;
  }
  return http<Product>(`/products/${id}`);
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
