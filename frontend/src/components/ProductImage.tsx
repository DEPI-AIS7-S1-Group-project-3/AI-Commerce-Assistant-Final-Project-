import { useState } from "react";
import { Headphones, Laptop, Package, Smartphone, type LucideIcon } from "lucide-react";
import type { Product } from "@/types";

const icons: Record<string, LucideIcon> = {
  mobiles: Smartphone,
  laptops: Laptop,
  audio: Headphones,
};

// Shows the first product image; falls back to a neutral category icon when there is
// no image yet (mock data has none) or the image fails to load.
export default function ProductImage({ product, className = "" }: { product: Product; className?: string }) {
  const [failed, setFailed] = useState(false);
  const image = product.images[0];

  if (!image || failed) {
    const Icon = icons[product.category.slug] ?? Package;
    return (
      <div className={`flex items-center justify-center bg-sand text-ink-soft/50 ${className}`} role="img" aria-label={product.title_ar}>
        <Icon className="h-1/4 w-1/4" strokeWidth={1.25} aria-hidden />
      </div>
    );
  }

  return (
    <img
      src={image.url}
      alt={image.alt_ar ?? product.title_ar}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  );
}
