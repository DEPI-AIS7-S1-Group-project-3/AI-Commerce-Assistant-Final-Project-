import { useEffect, useState } from "react";
import type { Brand, Category } from "@/types";

export interface FilterValues {
  category: string;
  brand: string;
  min_price: string;
  max_price: string;
  in_stock: boolean;
}

interface Props {
  values: FilterValues;
  categories: Category[];
  brands: Brand[];
  onChange: (patch: Partial<FilterValues>) => void;
  onReset: () => void;
}

export default function FilterPanel({ values, categories, brands, onChange, onReset }: Props) {
  // Price inputs are applied on blur/Enter so every keystroke does not refetch.
  const [min, setMin] = useState(values.min_price);
  const [max, setMax] = useState(values.max_price);

  useEffect(() => setMin(values.min_price), [values.min_price]);
  useEffect(() => setMax(values.max_price), [values.max_price]);

  const applyPrice = () => onChange({ min_price: min, max_price: max });

  return (
    <div className="space-y-6">
      <fieldset className="space-y-2">
        <legend className="mb-1 font-display text-base font-bold">الفئة</legend>
        {[{ slug: "", name_ar: "الكل" }, ...categories].map((c) => (
          <label key={c.slug} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name="category"
              className="accent-green"
              checked={values.category === c.slug}
              onChange={() => onChange({ category: c.slug })}
            />
            {c.name_ar}
          </label>
        ))}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="mb-1 font-display text-base font-bold">العلامة التجارية</legend>
        <select className="input" value={values.brand} onChange={(e) => onChange({ brand: e.target.value })} aria-label="العلامة التجارية">
          <option value="">الكل</option>
          {brands.map((b) => (
            <option key={b.slug} value={b.slug}>
              {b.name_ar ?? b.name}
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="mb-1 font-display text-base font-bold">السعر (ج.م)</legend>
        <div className="flex items-center gap-2">
          <input
            inputMode="numeric"
            className="input"
            placeholder="من"
            aria-label="أقل سعر"
            value={min}
            onChange={(e) => setMin(e.target.value.replace(/\D/g, ""))}
            onBlur={applyPrice}
            onKeyDown={(e) => e.key === "Enter" && applyPrice()}
          />
          <span className="text-ink-soft">-</span>
          <input
            inputMode="numeric"
            className="input"
            placeholder="إلى"
            aria-label="أعلى سعر"
            value={max}
            onChange={(e) => setMax(e.target.value.replace(/\D/g, ""))}
            onBlur={applyPrice}
            onKeyDown={(e) => e.key === "Enter" && applyPrice()}
          />
        </div>
      </fieldset>

      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="accent-green"
          checked={values.in_stock}
          onChange={(e) => onChange({ in_stock: e.target.checked })}
        />
        المتوفر في المخزون فقط
      </label>

      <button type="button" className="btn-ghost w-full" onClick={onReset}>
        مسح الفلاتر
      </button>
    </div>
  );
}
