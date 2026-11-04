import type { Product } from "@/types";
import { brand, cat, seller } from "./catalog";

// All figures are demo data. Mock products have NO images on purpose: random stock photos
// look wrong for electronics. <ProductImage> renders a category icon until real URLs exist.

type Seed = Omit<Product, "brand" | "category" | "seller" | "is_active" | "description_ar" | "images"> & {
  brandSlug: string;
  categorySlug: string;
  sellerId: number;
  description_ar?: string;
  imageSeed: string;
};

const seeds: Seed[] = [
  // Mobiles
  {
    id: 101, sku: "MOB-SAM-A55-256", title_ar: "سامسونج جالاكسي A55 بذاكرة 256 جيجابايت",
    price_egp: 15999, old_price_egp: 17499, stock_qty: 24, warranty_months: 24, is_returnable: true,
    specs: { ram_gb: 8, storage_gb: 256, screen_in: 6.6, battery_mah: 5000, camera_mp: 50 },
    rating_avg: 4.5, rating_count: 182, created_at: "2026-09-02T09:00:00Z",
    brandSlug: "samsung", categorySlug: "mobiles", sellerId: 1, imageSeed: "dalil-m1",
  },
  {
    id: 102, sku: "MOB-APL-IP15-128", title_ar: "آبل آيفون 15 بذاكرة 128 جيجابايت",
    price_egp: 42999, old_price_egp: null, stock_qty: 5, warranty_months: 12, is_returnable: true,
    specs: { ram_gb: 6, storage_gb: 128, screen_in: 6.1, battery_mah: 3349, camera_mp: 48 },
    rating_avg: 4.8, rating_count: 96, created_at: "2026-08-14T09:00:00Z",
    brandSlug: "apple", categorySlug: "mobiles", sellerId: 2, imageSeed: "dalil-m2",
  },
  {
    id: 103, sku: "MOB-XIA-RN13-256", title_ar: "شاومي ريدمي نوت 13 برو بذاكرة 256 جيجابايت",
    price_egp: 11499, old_price_egp: 12999, stock_qty: 40, warranty_months: 18, is_returnable: true,
    specs: { ram_gb: 8, storage_gb: 256, screen_in: 6.67, battery_mah: 5100, camera_mp: 200 },
    rating_avg: 4.4, rating_count: 311, created_at: "2026-09-20T09:00:00Z",
    brandSlug: "xiaomi", categorySlug: "mobiles", sellerId: 1, imageSeed: "dalil-m3",
  },
  {
    id: 104, sku: "MOB-SAM-S24-256", title_ar: "سامسونج جالاكسي S24 بذاكرة 256 جيجابايت",
    price_egp: 38999, old_price_egp: 41999, stock_qty: 0, warranty_months: 24, is_returnable: true,
    specs: { ram_gb: 8, storage_gb: 256, screen_in: 6.2, battery_mah: 4000, camera_mp: 50 },
    rating_avg: 4.7, rating_count: 74, created_at: "2026-07-30T09:00:00Z",
    brandSlug: "samsung", categorySlug: "mobiles", sellerId: 2, imageSeed: "dalil-m4",
  },
  // Laptops
  {
    id: 201, sku: "LAP-LEN-R7-16-512", title_ar: "لابتوب لينوفو آيديا باد 15.6 بوصة، معالج Ryzen 7",
    description_ar: "رام 16 جيجابايت وSSD بسعة 512 جيجابايت وشاشة IPS تغطي 100% من نطاق sRGB. مناسب للبرمجة والتصميم.",
    price_egp: 23499, old_price_egp: 25999, stock_qty: 7, warranty_months: 24, is_returnable: true,
    specs: { cpu: "Ryzen 7", ram_gb: 16, storage_gb: 512, screen_in: 15.6, weight_kg: 1.8, gpu: "مدمج" },
    rating_avg: 4.7, rating_count: 96, created_at: "2026-09-10T09:00:00Z",
    brandSlug: "lenovo", categorySlug: "laptops", sellerId: 1, imageSeed: "dalil-l1",
  },
  {
    id: 202, sku: "LAP-HP-I7-16-512", title_ar: "لابتوب إتش بي 14 بوصة، معالج Core i7",
    description_ar: "رام 16 جيجابايت وSSD بسعة 512 جيجابايت بوزن 1.4 كجم، مناسب للتنقل اليومي.",
    price_egp: 24900, old_price_egp: null, stock_qty: 3, warranty_months: 24, is_returnable: true,
    specs: { cpu: "Core i7", ram_gb: 16, storage_gb: 512, screen_in: 14, weight_kg: 1.4, gpu: "مدمج" },
    rating_avg: 4.5, rating_count: 58, created_at: "2026-09-18T09:00:00Z",
    brandSlug: "hp", categorySlug: "laptops", sellerId: 2, imageSeed: "dalil-l2",
  },
  {
    id: 203, sku: "LAP-LEN-RTX-16-1TB", title_ar: "لابتوب لينوفو ليجن 16 بوصة بكارت شاشة RTX 4050",
    description_ar: "رام 16 جيجابايت وSSD بسعة 1 تيرابايت وكارت شاشة مستقل للتصميم والألعاب.",
    price_egp: 24750, old_price_egp: 27500, stock_qty: 2, warranty_months: 24, is_returnable: true,
    specs: { cpu: "Core i5", ram_gb: 16, storage_gb: 1024, screen_in: 16, weight_kg: 2.3, gpu: "RTX 4050" },
    rating_avg: 4.7, rating_count: 41, created_at: "2026-10-01T09:00:00Z",
    brandSlug: "lenovo", categorySlug: "laptops", sellerId: 1, imageSeed: "dalil-l3",
  },
  {
    id: 204, sku: "LAP-HP-I3-8-256", title_ar: "لابتوب إتش بي 15.6 بوصة، معالج Core i3",
    price_egp: 13250, old_price_egp: 14500, stock_qty: 18, warranty_months: 12, is_returnable: true,
    specs: { cpu: "Core i3", ram_gb: 8, storage_gb: 256, screen_in: 15.6, weight_kg: 1.7, gpu: "مدمج" },
    rating_avg: 4.1, rating_count: 120, created_at: "2026-08-05T09:00:00Z",
    brandSlug: "hp", categorySlug: "laptops", sellerId: 2, imageSeed: "dalil-l4",
  },
  // Audio
  {
    id: 301, sku: "AUD-SON-WH1000", title_ar: "سماعة سوني لاسلكية بخاصية عزل الضوضاء",
    price_egp: 1850, old_price_egp: 2300, stock_qty: 120, warranty_months: 12, is_returnable: true,
    specs: { type: "فوق الأذن", anc: true, battery_hours: 30, bluetooth: "5.3" },
    rating_avg: 4.1, rating_count: 74, created_at: "2026-08-22T09:00:00Z",
    brandSlug: "sony", categorySlug: "audio", sellerId: 1, imageSeed: "dalil-a1",
  },
  {
    id: 302, sku: "AUD-ANK-Q30", title_ar: "سماعة أنكر ساوندكور Q30 بعزل ضوضاء نشط",
    price_egp: 2150, old_price_egp: null, stock_qty: 4, warranty_months: 18, is_returnable: true,
    specs: { type: "فوق الأذن", anc: true, battery_hours: 40, bluetooth: "5.0" },
    rating_avg: 4.6, rating_count: 203, created_at: "2026-09-25T09:00:00Z",
    brandSlug: "anker", categorySlug: "audio", sellerId: 2, imageSeed: "dalil-a2",
  },
  {
    id: 303, sku: "AUD-XIA-BUDS4", title_ar: "سماعة أذن شاومي Buds 4 لاسلكية",
    price_egp: 1290, old_price_egp: 1490, stock_qty: 65, warranty_months: 12, is_returnable: false,
    specs: { type: "داخل الأذن", anc: true, battery_hours: 9, bluetooth: "5.3" },
    rating_avg: 4.3, rating_count: 148, created_at: "2026-10-12T09:00:00Z",
    brandSlug: "xiaomi", categorySlug: "audio", sellerId: 1, imageSeed: "dalil-a3",
  },
  {
    id: 304, sku: "AUD-SAM-BUDS2", title_ar: "سماعة أذن سامسونج جالاكسي Buds 2 لاسلكية",
    price_egp: 2890, old_price_egp: 3290, stock_qty: 33, warranty_months: 24, is_returnable: false,
    specs: { type: "داخل الأذن", anc: true, battery_hours: 7, bluetooth: "5.3" },
    rating_avg: 4.4, rating_count: 87, created_at: "2026-07-18T09:00:00Z",
    brandSlug: "samsung", categorySlug: "audio", sellerId: 2, imageSeed: "dalil-a4",
  },
];

export const mockProducts: Product[] = seeds.map(
  // imageSeed is intentionally unused for now (kept so real image mapping can reuse it).
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ({ brandSlug, categorySlug, sellerId, imageSeed: _imageSeed, description_ar, ...rest }) => ({
    ...rest,
    description_ar: description_ar ?? "",
    is_active: true,
    images: [],
    brand: brand(brandSlug),
    category: cat(categorySlug),
    seller: seller(sellerId),
  }),
);
