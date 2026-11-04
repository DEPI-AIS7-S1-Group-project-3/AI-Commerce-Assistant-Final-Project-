// Types mirror the FastAPI backend where VERIFIED (see HANDOFF.md section 4).
// Anything marked UNVERIFIED is a best guess: check backend schemas / OpenAPI first.

export type SpecKind = "mobile" | "laptop" | "audio";

export interface Category {
  id: number;
  slug: string;
  name_ar: string;
  name_en: string;
  spec_kind: SpecKind | null;
}

export interface Brand {
  id: number;
  slug: string;
  name: string;
  name_ar: string | null;
}

export interface SellerSummary {
  id: number;
  store_name: string;
  rating: number | null;
}

export interface ProductImage {
  url: string;
  alt_ar: string | null;
}

// Product fields follow the DB `products` table. The nested objects (seller, brand,
// category, images) are a PROPOSED shape for a future GET /products response.
export interface Product {
  id: number;
  sku: string;
  title_ar: string;
  description_ar: string;
  price_egp: number;
  old_price_egp: number | null;
  stock_qty: number;
  warranty_months: number;
  is_returnable: boolean;
  is_active: boolean;
  specs: Record<string, string | number | boolean>;
  rating_avg: number | null;
  rating_count: number;
  created_at: string;
  images: ProductImage[];
  seller: SellerSummary;
  brand: Brand;
  category: Category;
}

export type ProductSort = "newest" | "price_asc" | "price_desc" | "rating";

// PROPOSED query params for GET /products (not agreed with backend yet).
export interface ProductQuery {
  q?: string;
  category?: string; // category slug
  brand?: string; // brand slug
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort?: ProductSort;
}

export interface CartLine {
  product_id: number;
  qty: number;
}

// Backend enums (VERIFIED)
export type OrderStatus =
  | "pending"
  | "confirmed"
  | "shipped"
  | "out_for_delivery"
  | "delivered"
  | "cancelled"
  | "return_requested"
  | "returned";

export type PaymentMethod = "cod" | "wallet" | "card";
