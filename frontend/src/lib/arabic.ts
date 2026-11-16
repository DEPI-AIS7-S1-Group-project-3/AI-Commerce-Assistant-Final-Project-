// Same idea as backend nlp/arabic.py (diacritics, alef forms, taa marbuta, Eastern digits),
// used only for the MOCK search. Real search will be done by the backend (pg_trgm).
const EASTERN = "٠١٢٣٤٥٦٧٨٩";

export function normalizeArabic(input: string): string {
  return input
    .toLowerCase()
    .replace(/[ً-ٰٟـ]/g, "") // diacritics + tatweel
    .replace(/[أإآ]/g, "ا")
    .replace(/ة/g, "ه")
    .replace(/ى/g, "ي")
    .replace(/[٠-٩]/g, (d) => String(EASTERN.indexOf(d)))
    .trim();
}
