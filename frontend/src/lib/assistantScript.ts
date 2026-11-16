import type { Product } from "@/types";
import type { Lang } from "@/lib/i18n";

export type Bi = Record<Lang, string>;
export type Followup = { label: Bi; query: string };
export type Reply = {
  text: Bi;
  productIds: number[];
  reasons: Bi[];
  followups: Followup[];
  confident: boolean;
};

export const suggestions: Followup[] = [
  {
    label: { ar: "لابتوب للبرمجة بحد أقصى 25,000 ج.م", en: "Programming laptop under EGP 25,000" },
    query: "laptop for programming under 25000",
  },
  {
    label: { ar: "هاتف بكاميرا ممتازة تحت 20,000 ج.م", en: "Phone with a great camera under EGP 20,000" },
    query: "phone with a great camera under 20000",
  },
  {
    label: { ar: "أرخص سماعة بعزل ضوضاء", en: "Cheapest noise-cancelling headphones" },
    query: "cheapest noise cancelling headphones",
  },
  { label: { ar: "منتجات سامسونج المتوفرة", en: "Samsung products in stock" }, query: "samsung" },
];

type Cat = "laptops" | "mobiles" | "audio";

const catWords: Record<Cat, string[]> = {
  laptops: ["laptop", "notebook", "programming", "لابتوب", "لاب توب", "لاب", "برمج"],
  mobiles: ["phone", "mobile", "camera", "هاتف", "موبايل", "تليفون", "جوال", "كاميرا"],
  audio: ["headphone", "earbud", "audio", "noise", "buds", "سماع", "صوت", "ضوضاء"],
};
const catNames: Record<Cat, Bi> = {
  laptops: { ar: "لابتوب", en: "laptops" },
  mobiles: { ar: "هاتف", en: "phones" },
  audio: { ar: "سماعة", en: "headphones" },
};
const catQuery: Record<Cat, string> = { laptops: "laptop", mobiles: "phone", audio: "headphones" };
const cheapWords = ["cheapest", "cheap", "lowest", "أرخص", "ارخص", "أقل سعر", "اقل سعر", "رخيص"];

const has = (s: string, words: string[]) => words.some((w) => s.includes(w));
const fmt = (n: number) => n.toLocaleString("en-US");

function parseBudget(raw: string): number | null {
  const s = raw
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)))
    .replace(/(\d),(\d)/g, "$1$2")
    // drop spec numbers like 16GB, 256 GB, 5000mAh
    .replace(/\d+(?:\.\d+)?\s*(gb|tb|mah|mp|inch|جيجا|تيرا|بوصة)/gi, " ");
  const m = s.match(/(\d+(?:\.\d+)?)\s*(k|ألف|الف)?/i);
  if (!m) return null;
  const n = parseFloat(m[1]) * (m[2] ? 1000 : 1);
  return n >= 500 ? n : null;
}

function reasonFor(p: Product, i: number, budget: number | null, cheapest: boolean): Bi {
  if (i === 0 && cheapest) return { ar: "الأقل سعرًا ضمن النتائج", en: "Lowest price among the results" };
  if (i === 0) {
    const r = p.rating_avg?.toFixed(1) ?? "-";
    return { ar: `الأعلى تقييمًا (${r}) ضمن النتائج`, en: `Highest rated (${r}) among the results` };
  }
  if (budget) return { ar: `ضمن ميزانيتك (${fmt(budget)} ج.م)`, en: `Within your budget (EGP ${fmt(budget)})` };
  return { ar: "بديل بتقييم وسعر قريبين", en: "Alternative with a close rating and price" };
}

// Scripted logic over the real (mock) catalog. No LLM, no network.
export function scriptedReply(input: string, products: Product[]): Reply {
  const s = input.toLowerCase();
  const cat = (Object.keys(catWords) as Cat[]).find((c) => has(s, catWords[c])) ?? null;
  const brand = products.map((p) => p.brand).find((b) => s.includes(b.slug) || s.includes(b.name.toLowerCase()) || (b.name_ar && s.includes(b.name_ar))) ?? null;
  const budget = parseBudget(s);
  const cheapest = has(s, cheapWords);

  if (!cat && !brand && !budget && !cheapest) {
    return {
      confident: false,
      productIds: [],
      reasons: [],
      followups: suggestions.slice(0, 3),
      text: {
        ar: "لست متأكدًا من فهم طلبك. اذكر الفئة (لابتوب، هاتف، سماعة) أو الميزانية أو الماركة، أو اختر أحد الاقتراحات.",
        en: "I am not sure I understood. Mention a category (laptop, phone, headphones), a budget or a brand, or pick a suggestion.",
      },
    };
  }

  const matches = products
    .filter((p) => p.stock_qty > 0)
    .filter((p) => !cat || p.category.slug === cat)
    .filter((p) => !brand || p.brand.slug === brand.slug)
    .filter((p) => !budget || p.price_egp <= budget)
    .sort((a, b) =>
      cheapest ? a.price_egp - b.price_egp : (b.rating_avg ?? 0) - (a.rating_avg ?? 0) || a.price_egp - b.price_egp,
    )
    .slice(0, 3);

  const budgetAr = budget ? ` بحد أقصى ${fmt(budget)} ج.م` : "";
  const budgetEn = budget ? ` under EGP ${fmt(budget)}` : "";
  const label = cat ? catNames[cat] : { ar: "منتج", en: "products" };
  const brandAr = brand ? ` من ${brand.name_ar ?? brand.name}` : "";
  const brandEn = brand ? `${brand.name} ` : "";

  if (matches.length === 0) {
    return {
      confident: false,
      productIds: [],
      reasons: [],
      followups: cat
        ? [{ label: { ar: "أرني الأرخص في هذه الفئة", en: "Show the cheapest in this category" }, query: `cheapest ${catQuery[cat]}` }]
        : suggestions.slice(0, 2),
      text: {
        ar: `لا توجد ${label.ar} متاحة${brandAr}${budgetAr} حاليًا. جرّب رفع الميزانية أو تغيير الفئة.`,
        en: `No ${brandEn}${label.en} in stock${budgetEn} right now. Try a higher budget or another category.`,
      },
    };
  }

  const followups: Followup[] = [];
  if (!cheapest) {
    followups.push({
      label: { ar: "أرني الأرخص", en: "Show the cheapest" },
      query: `cheapest ${cat ? catQuery[cat] : ""} ${brand ? brand.slug : ""}`.trim(),
    });
  }
  (Object.keys(catNames) as Cat[])
    .filter((c) => c !== cat)
    .slice(0, 2)
    .forEach((c) =>
      followups.push({
        label: { ar: `أرني ${catNames[c].ar}`, en: `Show ${catNames[c].en}` },
        query: catQuery[c],
      }),
    );

  return {
    confident: true,
    productIds: matches.map((p) => p.id),
    reasons: matches.map((p, i) => reasonFor(p, i, budget, cheapest)),
    followups,
    text: {
      ar: `وجدت ${matches.length} ${label.ar}${brandAr} متاحة${budgetAr}، مرتبة ${cheapest ? "من الأقل سعرًا" : "حسب التقييم"}.`,
      en: `I found ${matches.length} ${brandEn}${label.en} in stock${budgetEn}, ranked ${cheapest ? "by lowest price" : "by rating"}.`,
    },
  };
}

// Fake step timings for the developer trace panel (labelled as simulated in the UI).
export function traceFor(reply: Reply) {
  const steps = [
    { name: "input_guardrail", ms: 12 },
    { name: "supervisor", ms: 240 },
  ];
  if (reply.confident) steps.push({ name: "search_products", ms: 180 }, { name: "check_stock", ms: 95 });
  steps.push({ name: "output_guardrail", ms: 18 });
  return steps;
}