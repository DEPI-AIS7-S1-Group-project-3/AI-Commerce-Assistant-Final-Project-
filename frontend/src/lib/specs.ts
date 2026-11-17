import type { Lang, TKey } from "@/lib/i18n";
import { fill } from "@/lib/format";

type T = (k: TKey) => string;
type SpecValue = string | number | boolean;

// Display order per category. Keys match backend schemas/specs.py (SPEC_MODELS).
const ORDER: Record<string, string[]> = {
  mobile: ["ram_gb", "storage_gb", "screen_inch", "battery_mah", "camera_mp", "network", "os", "color_ar"],
  laptop: ["cpu", "ram_gb", "storage_gb", "storage_type", "gpu", "screen_inch", "battery_hours", "weight_kg", "os"],
  audio: ["type", "wireless", "noise_cancelling", "battery_hours", "connector"],
};

// Keys/values that have a dictionary entry (t() throws on unknown keys, so check first).
const LABELED = new Set(Object.values(ORDER).flat());
const TYPES = new Set(["earbuds", "headphones", "speaker", "charger", "power_bank", "cable"]);

// Fixed technical names: same in both languages.
const PLAIN: Record<string, string> = {
  android: "Android", ios: "iOS", windows: "Windows", macos: "macOS",
  "4g": "4G", "5g": "5G", ssd: "SSD", hdd: "HDD",
  usb_c: "USB-C", lightning: "Lightning", "3.5mm": "3.5 mm", bluetooth: "Bluetooth",
};

function value(key: string, v: SpecValue, t: T): string {
  if (typeof v === "boolean") return t(v ? "spec.yes" : "spec.no");
  const n = typeof v === "number" ? v : Number(v);
  switch (key) {
    case "ram_gb":
      return fill(t("unit.gb"), { n });
    case "storage_gb":
      return n >= 1024 && n % 1024 === 0 ? fill(t("unit.tb"), { n: n / 1024 }) : fill(t("unit.gb"), { n });
    case "screen_inch":
      return fill(t("unit.inch"), { n });
    case "battery_mah":
      return fill(t("unit.mah"), { n });
    case "camera_mp":
      return fill(t("unit.mp"), { n });
    case "battery_hours":
      return fill(t("unit.hours"), { n });
    case "weight_kg":
      return fill(t("unit.kg"), { n });
    case "os":
      return v === "none" ? t("spec.os.none") : (PLAIN[String(v)] ?? String(v));
    case "type":
      return TYPES.has(String(v)) ? t(`spec.type.${v}` as TKey) : String(v);
    default:
      return PLAIN[String(v)] ?? String(v);
  }
}

export interface SpecRow {
  key: string;
  label: string;
  value: string;
}

/** Turn a product's specs JSON into translated rows, in a fixed order. Unknown keys come last. */
export function specRows(specs: Record<string, SpecValue>, kind: string | null, t: T, _lang?: Lang): SpecRow[] {
  const order = ORDER[kind ?? ""] ?? [];
  const keys = [...order.filter((k) => k in specs), ...Object.keys(specs).filter((k) => !order.includes(k))];
  return keys
    .filter((k) => specs[k] !== null && specs[k] !== undefined && specs[k] !== "")
    .map((k) => ({ key: k, label: LABELED.has(k) ? t(`spec.${k}` as TKey) : k, value: value(k, specs[k], t) }));
}
