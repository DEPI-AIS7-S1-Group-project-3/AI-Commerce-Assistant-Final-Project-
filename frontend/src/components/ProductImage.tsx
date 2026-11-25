import { useState } from "react";
import { Headphones, Laptop, Package, Smartphone, type LucideIcon } from "lucide-react";
import type { Product } from "@/types";

const icons: Record<string, LucideIcon> = {
  mobiles: Smartphone,
  phones: Smartphone,
  laptops: Laptop,
  audio: Headphones,
};

// Shows the first product image; falls back to a neutral category icon when there is
// no image yet or the image fails to load.
export default function ProductImage({
  product,
  categorySlug,
  title,
  className = "",
}: {
  product?: Partial<Product>;
  categorySlug?: string;
  title?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const image = product?.images?.[0];
  const catSlug = product?.category?.slug ?? categorySlug ?? "";
  const label = product?.title_ar ?? title ?? "Product";

  if (!image || failed) {
    const Icon = icons[catSlug] ?? Package;
    return (
      <div className={`flex items-center justify-center bg-sand text-ink-soft/50 ${className}`} role="img" aria-label={label}>
        <Icon className="h-2/3 w-2/3 max-h-8 max-w-8" strokeWidth={1.5} aria-hidden />
      </div>
    );
  }

  return (
    <img
      src={image.url}
      alt={image.alt_ar ?? label}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  );
}
