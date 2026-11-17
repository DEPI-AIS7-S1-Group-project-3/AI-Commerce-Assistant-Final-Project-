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
  title_en?: string | null; // optional English title from the backend; null/missing = use title_ar
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

// GET /products/{id}/reviews (backend reviews API, public)
export interface Review {
  id: number;
  rating: number;
  body: string;
  author_name: string; // first name only
  is_verified_purchase: boolean;
  created_at: string;
}

export interface ProductReviews {
  product_id: number;
  rating_avg: number | null;
  rating_count: number;
  distribution: Record<"1" | "2" | "3" | "4" | "5", number>;
  total: number;
  reviews: Review[];
}

// /addresses (VERIFIED against backend schemas/address.py)
export interface Address {
  id: number;
  label: string | null;
  recipient_name: string;
  phone: string;
  governorate: string; // stored in Arabic, e.g. "القاهرة"
  city: string;
  street_address: string;
  is_default: boolean;
}
export type AddressInput = Omit<Address, "id">;

// POST /orders (VERIFIED against backend schemas/order.py). Decimals come as strings.
export type ReturnReason = "defective" | "not_as_described" | "changed_mind" | "wrong_item" | "damaged_in_shipping" | "other";
export type ReturnStatus = "requested" | "approved" | "rejected" | "received" | "refunded";

export interface OrderItem {
  id: number; // order item id (for return requests)
  product_id: number;
  title: string;
  qty: number;
  unit_price_egp: number;
  line_total_egp: number;
  is_returnable: boolean;
  return_status: ReturnStatus | null;
  can_return: boolean; // computed by the backend with its own return rules
  return_block: string | null; // why not: not_delivered, window_expired, ...
}
export interface Order {
  id: number;
  checkout_group_id: string; // same for all packages of one checkout
  seller_id: number;
  seller_name: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  payment_status: "pending" | "paid" | "failed" | "refunded";
  shipping_address: Partial<Address>;
  subtotal_egp: number;
  shipping_fee_egp: number;
  total_egp: number;
  expected_delivery_at: string;
  delivered_at: string | null;
  created_at: string;
  can_cancel: boolean; // computed by the backend
  cancel_block: string | null; // why not: already_shipped, ...
  items: OrderItem[];
}
export interface TimelineEntry {
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  actor_type: string;
  created_at: string;
}
export interface OrderDetail extends Order {
  timeline: TimelineEntry[];
}
export interface CheckoutResult {
  checkout_group_id: string;
  orders: Order[];
}
// 409 checkout_unavailable details: one entry per problem line
export interface CheckoutProblem {
  product_id: number;
  reason: "unavailable" | "insufficient_stock";
  available?: number;
}

// /policies (backend schemas/policy.py). Arabic only for now.
export interface PolicySummary {
  slug: string;
  category: string;
  title_ar: string;
  version: string;
}
export interface PolicySection {
  no: number;
  title: string;
  body: string;
}
export interface Policy extends PolicySummary {
  body_md: string;
  sections: PolicySection[];
}
