"""Generate data/raw/products.json deterministically (random seed = 42).

Run once and commit the JSON:  uv run python scripts/generate_products.py
"""
import json
import random
from pathlib import Path

from ai_commerce_marketplace.schemas.specs import validate_specs

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "products.json"
rng = random.Random(42)

SELLERS = ["تك ستور مصر", "نيل إلكترونيكس", "دلتا ديجيتال", "ماستر جادجت"]
BRANDS_AR = {
    "samsung": "سامسونج", "apple": "أبل", "xiaomi": "شاومي", "oppo": "أوبو",
    "realme": "ريلمي", "lenovo": "لينوفو", "hp": "إتش بي", "dell": "ديل",
    "asus": "أسوس", "anker": "أنكر", "jbl": "جي بي إل", "baseus": "بيسوس",
}
COLORS = ["أسود", "أزرق", "أبيض", "أخضر", "رمادي", "ذهبي", "بنفسجي"]

# حالات خاصة مطلوبة في الـ spec (فهرس المنتج جوه فئته)
INACTIVE = {("mobiles", 14), ("laptops", 13), ("audio", 12)}   # 3 منتجات غير نشطة
OUT_OF_STOCK = {("mobiles", 5), ("audio", 7)}                    # 2 مخزون صفر
NOT_RETURNABLE = {("audio", 1)}                                  # سماعات أذن: غير قابلة للإرجاع

_used_codes: set[str] = set()


def series_code() -> str:
    while True:
        code = f"{rng.choice('ABCDEFGHKLMNPRSTVXZ')}{rng.randint(1, 9)}{rng.choice('05')}"
        if code not in _used_codes:
            _used_codes.add(code)
            return code


def price(x: float) -> int:
    """17999 بدل 18012: شكل أسعار المتاجر."""
    return int(round(x, -2)) - 1


def old_price_for(p: int) -> int | None:
    return price(p * rng.uniform(1.08, 1.2)) if rng.random() < 0.35 else None


def build(sku, cat, idx, seller_offset, kind, title, desc, p, warranty, specs):
    n_images = rng.choice([1, 2, 3])
    return {
        "sku": sku,
        "seller_store_name": SELLERS[(idx + seller_offset) % 4],
        "category_slug": cat,
        "brand_slug": specs.pop("_brand"),
        "title_ar": title,
        "description_ar": desc,
        "price_egp": p,
        "old_price_egp": old_price_for(p),
        "stock_qty": 0 if (cat, idx) in OUT_OF_STOCK else rng.randint(3, 60),
        "warranty_months": warranty,
        "is_returnable": (cat, idx) not in NOT_RETURNABLE,
        "is_active": (cat, idx) not in INACTIVE,
        "specs": validate_specs(kind, specs),
        "images": [
            {"url": f"/static/products/{sku}-{k}.jpg", "alt_ar": f"{title} - صورة {k}", "sort_order": k - 1}
            for k in range(1, n_images + 1)
        ],
    }


# ───────────── موبايلات ─────────────
MOBILE_TIERS = {
    "budget": dict(ram=[3, 4, 6], storage=[32, 64, 128], screen=(6.1, 6.7), battery=(4000, 5000),
                   camera=[8, 13, 50], network="4g", price=(3500, 7000), warranty=12),
    "mid": dict(ram=[6, 8], storage=[128, 256], screen=(6.4, 6.7), battery=(4500, 5500),
                camera=[50, 64, 108], network="5g", price=(8000, 16000), warranty=12),
    "flagship": dict(ram=[8, 12, 16], storage=[256, 512, 1024], screen=(6.5, 6.9), battery=(4500, 5500),
                     camera=[50, 108, 200], network="5g", price=(22000, 55000), warranty=24),
}
MOBILE_PLAN = [
    ("realme", "budget"), ("xiaomi", "budget"), ("oppo", "budget"), ("samsung", "budget"), ("xiaomi", "budget"),
    ("realme", "mid"), ("oppo", "mid"), ("samsung", "mid"), ("xiaomi", "mid"), ("samsung", "mid"), ("apple", "mid"),
    ("samsung", "flagship"), ("apple", "flagship"), ("xiaomi", "flagship"), ("oppo", "flagship"),
]


def make_mobile(i, brand, tier):
    t = MOBILE_TIERS[tier]
    ios = brand == "apple"
    ram = rng.choice([4, 6, 8] if ios else t["ram"])
    s_idx = rng.randrange(len(t["storage"]))
    storage = t["storage"][s_idx]
    screen = round(rng.uniform(*t["screen"]), 1)
    battery = int(round(rng.uniform(3200, 4400) if ios else rng.uniform(*t["battery"]), -2))
    camera = 12 if ios else rng.choice(t["camera"])
    lo, hi = t["price"]
    p = price(lo + (s_idx + rng.random()) / len(t["storage"]) * (hi - lo))
    brand_ar = BRANDS_AR[brand]
    net_ar = "الجيل الخامس 5G" if t["network"] == "5g" else "الجيل الرابع 4G"
    specs = dict(
        _brand=brand, ram_gb=ram, storage_gb=storage, screen_inch=screen, battery_mah=battery,
        camera_mp=camera, os="ios" if ios else "android", network=t["network"], color_ar=rng.choice(COLORS),
    )
    title = f"موبايل {brand_ar} سلسلة {series_code()} تجريبية {ram} رام {storage} جيجا"
    desc = (f"موبايل {brand_ar} بشاشة {screen} بوصة وذاكرة {ram} جيجا رام ومساحة تخزين {storage} جيجا. "
            f"بطارية {battery} مللي أمبير وكاميرا رئيسية {camera} ميجابكسل، ويدعم شبكات {net_ar}.")
    return build(f"MOB-{i + 1:03d}", "mobiles", i, 0, "mobile", title, desc, p, t["warranty"], specs)


# ───────────── لابتوبات ─────────────
LAPTOP_TIERS = [
    dict(cpu=["Core i3-12th", "Ryzen 3"], ram=[4, 8], storage=[256, 512], screen=[14, 15.6],
         weight=(1.6, 2.0), battery=(5, 8), gpu="مدمج", price=(11000, 17000), warranty=12),
    dict(cpu=["Core i5-12th", "Ryzen 5"], ram=[8, 16], storage=[512, 512], screen=[14, 15.6],
         weight=(1.3, 1.9), battery=(7, 11), gpu="مدمج", price=(19000, 30000), warranty=12),
    dict(cpu=["Core i7-13th", "Ryzen 7"], ram=[16, 32], storage=[512, 1024], screen=[14, 16],
         weight=(1.2, 1.8), battery=(8, 14), gpu="مدمج", price=(32000, 52000), warranty=24),
    dict(cpu=["Core i7-13th", "Ryzen 7"], ram=[16, 32], storage=[1024, 1024], screen=[15.6, 17.3],
         weight=(2.2, 3.0), battery=(4, 6), gpu="كارت منفصل 6 جيجا", price=(38000, 70000), warranty=24),
]
LAPTOP_PLAN = [
    ("lenovo", 0), ("hp", 0), ("dell", 0), ("asus", 0),
    ("hp", 1), ("lenovo", 1), ("asus", 1), ("dell", 1), ("lenovo", 1),
    ("dell", 2), ("apple", 2), ("asus", 2),
    ("asus", 3), ("lenovo", 3), ("hp", 3),
]


def make_laptop(i, brand, tier_idx):
    t = LAPTOP_TIERS[tier_idx]
    apple = brand == "apple"
    r_idx = rng.randrange(len(t["ram"]))
    ram = t["ram"][r_idx]
    storage = rng.choice(t["storage"])
    stype = "hdd" if (tier_idx == 0 and rng.random() < 0.25) else "ssd"
    if stype == "hdd":
        storage = 1000
    os_ = "macos" if apple else ("none" if tier_idx == 0 and rng.random() < 0.3 else "windows")
    cpu = "Apple Silicon" if apple else rng.choice(t["cpu"])
    screen = rng.choice([13.6, 14, 16] if apple else t["screen"])
    weight = round(rng.uniform(1.2, 1.6) if apple else rng.uniform(*t["weight"]), 1)
    battery = rng.randint(*t["battery"])
    lo, hi = t["price"]
    p = price(lo + (r_idx + rng.random()) / len(t["ram"]) * (hi - lo))
    brand_ar = BRANDS_AR[brand]
    storage_label = "1 تيرا" if storage >= 1000 else f"{storage} جيجا"
    specs = dict(
        _brand=brand, ram_gb=ram, storage_gb=storage, storage_type=stype, cpu=cpu, gpu=t["gpu"],
        screen_inch=screen, weight_kg=weight, battery_hours=battery, os=os_,
    )
    title = f"لابتوب {brand_ar} سلسلة {series_code()} تجريبية {ram} رام {storage_label}"
    desc = (f"لابتوب {brand_ar} بمعالج {cpu} وذاكرة {ram} جيجا رام وتخزين {storage_label} {stype.upper()}. "
            f"شاشة {screen} بوصة ووزن {weight} كجم وبطارية تدوم حتى {battery} ساعات. كارت الشاشة: {t['gpu']}.")
    return build(f"LAP-{i + 1:03d}", "laptops", i, 1, "laptop", title, desc, p, t["warranty"], specs)


# ───────────── سماعات وإكسسوارات ─────────────
# (النوع، الماركة، كود الموديل، لاسلكي، ساعات البطارية، عزل ضوضاء، الموصل، السعر، الضمان)
AUDIO_PLAN = [
    ("earbuds", "jbl", "E10", True, 24, False, "bluetooth", 1499, 12),
    ("earbuds", "anker", "E20", True, 30, True, "bluetooth", 2399, 18),
    ("earbuds", "xiaomi", "E30", True, 18, False, "bluetooth", 899, 12),
    ("headphones", "jbl", "H10", True, 40, False, "bluetooth", 2199, 12),
    ("headphones", "anker", "H20", True, 60, True, "bluetooth", 3999, 18),
    ("headphones", "baseus", "H30", False, None, False, "3.5mm", 699, 6),
    ("speaker", "jbl", "S10", True, 12, None, "bluetooth", 2899, 12),
    ("speaker", "anker", "S20", True, 24, None, "bluetooth", 1999, 12),
    ("charger", "anker", "C10", False, None, None, "usb_c", 749, 18),
    ("charger", "baseus", "C20", False, None, None, "usb_c", 549, 12),
    ("power_bank", "anker", "P10", False, None, None, "usb_c", 1299, 18),
    ("power_bank", "baseus", "P20", False, None, None, "usb_c", 999, 12),
    ("cable", "baseus", "K10", False, None, None, "usb_c", 199, 6),
    ("cable", "anker", "K20", False, None, None, "lightning", 349, 12),
    ("cable", "xiaomi", "K30", False, None, None, "usb_c", 149, 6),
]
AUDIO_BASE = {
    "earbuds": "سماعات أذن", "headphones": "سماعة رأس", "speaker": "سماعة بلوتوث محمولة",
    "charger": "شاحن سريع", "power_bank": "باور بانك", "cable": "كابل شحن",
}


def make_audio(i, type_, brand, code, wireless, hours, nc, connector, p, warranty):
    base = AUDIO_BASE[type_]
    if type_ in ("earbuds", "headphones"):
        base += " لاسلكية" if wireless else " سلكية"
    brand_ar = BRANDS_AR[brand]
    title = f"{base} {brand_ar} موديل تجريبي {code}"
    desc = f"{base} من {brand_ar} بجودة مناسبة للاستخدام اليومي"
    if hours:
        desc += f"، وبطارية تعمل حتى {hours} ساعة"
    if nc:
        desc += "، مع خاصية عزل الضوضاء"
    desc += "."
    specs = dict(_brand=brand, type=type_, wireless=wireless, battery_hours=hours,
                 noise_cancelling=nc, connector=connector)
    return build(f"AUD-{i + 1:03d}", "audio", i, 2, "audio", title, desc, p, warranty, specs)


def main() -> None:
    products = [make_mobile(i, b, t) for i, (b, t) in enumerate(MOBILE_PLAN)]
    products += [make_laptop(i, b, t) for i, (b, t) in enumerate(LAPTOP_PLAN)]
    products += [make_audio(i, *row) for i, row in enumerate(AUDIO_PLAN)]
    assert len(products) == 45
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(products)} products to {OUT}")


if __name__ == "__main__":
    main()