import type { Brand, Category, Product, SellerSummary } from "@/types";
import type { Lang } from "@/lib/i18n";

// English names for mock products (keyed by product id). Falls back to Arabic if missing.
const titlesEn: Record<number, string> = {
  101: "Samsung Galaxy A55 256GB",
  102: "Apple iPhone 15 128GB",
  103: "Xiaomi Redmi Note 13 Pro 256GB",
  104: "Samsung Galaxy S24 256GB",
  201: "Lenovo IdeaPad 15.6\" Laptop, Ryzen 7",
  202: "HP 14\" Laptop, Core i7",
  203: "Lenovo Legion 16\" Laptop, RTX 4050",
  204: "HP 15.6\" Laptop, Core i3",
  301: "Sony Wireless Noise-Cancelling Headphones",
  302: "Anker Soundcore Q30 Active Noise Cancelling Headphones",
  303: "Xiaomi Buds 4 Wireless Earbuds",
  304: "Samsung Galaxy Buds 2 Wireless Earbuds",
};

const sellersEn: Record<number, string> = {
  1: "Al Nile Store",
  2: "Digital Mall",
};

export const productTitle = (p: Product, lang: Lang) =>
  lang === "en" ? (titlesEn[p.id] ?? p.title_ar) : p.title_ar;

export const sellerName = (s: SellerSummary, lang: Lang) =>
  lang === "en" ? (sellersEn[s.id] ?? s.store_name) : s.store_name;

export const brandName = (b: Brand, lang: Lang) => (lang === "en" ? b.name : (b.name_ar ?? b.name));

export const categoryName = (c: Category, lang: Lang) => (lang === "en" ? c.name_en : c.name_ar);