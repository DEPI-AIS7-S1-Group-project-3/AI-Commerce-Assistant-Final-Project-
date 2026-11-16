import type { Brand, Category, SellerSummary } from "@/types";

export const categories: Category[] = [
  { id: 2, slug: "mobiles", name_ar: "الهواتف المحمولة", name_en: "Mobiles", spec_kind: "mobile" },
  { id: 3, slug: "laptops", name_ar: "أجهزة اللابتوب", name_en: "Laptops", spec_kind: "laptop" },
  { id: 4, slug: "audio", name_ar: "السماعات والصوتيات", name_en: "Audio", spec_kind: "audio" },
];

export const brands: Brand[] = [
  { id: 1, slug: "samsung", name: "Samsung", name_ar: "سامسونج" },
  { id: 2, slug: "apple", name: "Apple", name_ar: "آبل" },
  { id: 3, slug: "xiaomi", name: "Xiaomi", name_ar: "شاومي" },
  { id: 4, slug: "lenovo", name: "Lenovo", name_ar: "لينوفو" },
  { id: 5, slug: "anker", name: "Anker", name_ar: "أنكر" },
  { id: 6, slug: "hp", name: "HP", name_ar: "إتش بي" },
  { id: 7, slug: "sony", name: "Sony", name_ar: "سوني" },
];

export const sellers: SellerSummary[] = [
  { id: 1, store_name: "متجر النيل", rating: 4.7 },
  { id: 2, store_name: "ديجيتال مول", rating: 4.5 },
];

export const cat = (slug: string) => categories.find((c) => c.slug === slug)!;
export const brand = (slug: string) => brands.find((b) => b.slug === slug)!;
export const seller = (id: number) => sellers.find((s) => s.id === id)!;
