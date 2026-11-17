import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "ar" | "en";

// Add new strings here: key -> { ar, en }
const dict = {
  "nav.assistant": { ar: "المساعد الذكي", en: "AI Assistant" },
  "nav.products": { ar: "المنتجات", en: "Products" },
  "nav.cart": { ar: "السلة", en: "Cart" },
  "nav.login": { ar: "تسجيل الدخول", en: "Log in" },
  "nav.search": { ar: "ابحث عن منتج", en: "Search products" },
  "lang.switch": { ar: "English", en: "العربية" },
  "theme.toLight": { ar: "الوضع الفاتح", en: "Light mode" },
  "theme.toDark": { ar: "الوضع الداكن", en: "Dark mode" },
  "tagline": {
    ar: "تكنولوجيا أقرب ليك.",
    en: "Your neighborhood tech shop, only smarter.",
  }, 
    "nav.shop": { ar: "تسوق", en: "Shop" },
  "nav.main": { ar: "التنقل الرئيسي", en: "Main navigation" },
  "assistant.title": { ar: "المساعد الذكي", en: "AI Assistant" },
  "assistant.soon": {
    ar: "واجهة المحادثة قيد البناء. ستجد هنا توصيات مقارنة وحالة المخزون.",
    en: "The chat interface is being built. You will get comparisons and stock status here.",
  },
    "home.title1": { ar: "ابحث، قارن،", en: "Search, compare," },
  "home.title2": { ar: "واشترِ بثقة.", en: "and buy with confidence." },
  "home.sub": {
    ar: "نعرض لك المواصفات بوضوح، والمخزون الفعلي، وسياسات الاسترجاع والضمان قبل الدفع.",
    en: "We show clear specs, real stock, return and warranty policies before you pay.",
  },
  "home.browse": { ar: "تصفح المنتجات", en: "Browse products" },
  "home.cheapest": { ar: "الأقل سعرًا أولًا", en: "Lowest price first" },
  "home.delivery.v": { ar: "3 أيام", en: "3 days" },
  "home.delivery.l": { ar: "موعد التسليم المتوقع", en: "Expected delivery" },
  "home.return.v": { ar: "14 يومًا", en: "14 days" },
  "home.return.l": { ar: "مهلة طلب الاسترجاع بعد التسليم", en: "Return window after delivery" },
  "home.ship.v": { ar: "مجاني", en: "Free" },
  "home.ship.l": { ar: "الشحن للطلبات من 5,000 ج.م", en: "Shipping on orders from EGP 5,000" },
  "home.categories": { ar: "تسوق حسب الفئة", en: "Shop by category" },
  "cat.mobiles": { ar: "الهواتف المحمولة", en: "Mobile phones" },
  "cat.mobiles.d": { ar: "من الفئة الاقتصادية إلى الرائدة", en: "From budget to flagship" },
  "cat.laptops": { ar: "أجهزة اللابتوب", en: "Laptops" },
  "cat.laptops.d": { ar: "للدراسة والعمل والتصميم", en: "For study, work and design" },
  "cat.audio": { ar: "السماعات والصوتيات", en: "Headphones and audio" },
  "cat.audio.d": { ar: "عزل الضوضاء وجودة الصوت", en: "Noise isolation and sound quality" },
    "home.top": { ar: "الأعلى تقييمًا", en: "Top rated" },
  "home.viewall": { ar: "عرض الكل", en: "View all" },
  "footer.desc": {
    ar: "تكنولوجيا أقرب ليك. نقارن لك الخيارات، ونعرض لك المخزون الحقيقي والسعر الواضح.",
    en: "Your neighborhood tech shop, only smarter. We compare options and show real stock and clear prices.",
  },
  "footer.policies": { ar: "السياسات", en: "Policies" },
  "policy.shipping": { ar: "سياسة الشحن", en: "Shipping policy" },
  "policy.returns": { ar: "سياسة الاسترجاع", en: "Returns policy" },
  "policy.warranty": { ar: "سياسة الضمان", en: "Warranty policy" },
  "policy.cancellation": { ar: "سياسة الإلغاء", en: "Cancellation policy" },
  "footer.note": {
    ar: "مشروع تخرج. جميع المنتجات والأسعار المعروضة بيانات تجريبية.",
    en: "Graduation project. All products and prices shown are demo data.",
  },
    "sort.newest": { ar: "الأحدث", en: "Newest" },
  "sort.price_asc": { ar: "السعر: من الأقل إلى الأعلى", en: "Price: low to high" },
  "sort.price_desc": { ar: "السعر: من الأعلى إلى الأقل", en: "Price: high to low" },
  "sort.rating": { ar: "الأعلى تقييمًا", en: "Top rated" },
  "products.all": { ar: "جميع المنتجات", en: "All products" },
  "products.search": { ar: "نتائج البحث:", en: "Search results:" },
  "products.loading": { ar: "جارٍ التحميل", en: "Loading" },
  "products.filters": { ar: "الفلاتر", en: "Filters" },
  "products.sort": { ar: "الترتيب", en: "Sort" },
  "products.list": { ar: "قائمة المنتجات", en: "Product list" },
  "products.error": { ar: "تعذر تحميل المنتجات.", en: "Could not load products." },
  "products.retry": { ar: "إعادة المحاولة", en: "Try again" },
  "products.empty.title": { ar: "لا توجد منتجات مطابقة", en: "No matching products" },
  "products.empty.hint": {
    ar: "جرّب تغيير كلمات البحث أو إزالة بعض الفلاتر.",
    en: "Try different search words or remove some filters.",
  },
  "products.clear": { ar: "مسح الفلاتر", en: "Clear filters" },
  "products.close": { ar: "إغلاق", en: "Close" },
  "products.show": { ar: "عرض النتائج", en: "Show results" },
  "card.reviews": { ar: "تقييم", en: "reviews" },
  "card.seller": { ar: "البائع", en: "Seller" },
  "card.add": { ar: "أضف إلى السلة", en: "Add to cart" },
  "card.soldout": { ar: "غير متوفر", en: "Out of stock" },
  "stock.in": { ar: "متاح في المخزون", en: "In stock" },
    "as.sub": {
    ar: "اسأل عن الهواتف واللابتوب والسماعات. الإجابات تعتمد على المخزون الفعلي في الكتالوج.",
    en: "Ask about phones, laptops and audio. Answers use real stock from the catalog.",
  },
  "as.placeholder": { ar: "اكتب سؤالك هنا", en: "Type your question" },
  "as.send": { ar: "إرسال", en: "Send" },
  "as.chip.laptop": { ar: "أفضل لابتوب للبرمجة", en: "Best laptop for programming" },
  "as.chip.phone": { ar: "هاتف بكاميرا ممتازة", en: "Phone with a great camera" },
  "as.chip.audio": { ar: "سماعة بعزل ضوضاء", en: "Noise-cancelling headphones" },
  "as.checking": { ar: "جارٍ التحقق من المخزون", en: "Checking stock" },
  "as.trace": { ar: "تفاصيل المعالجة", en: "Processing details" },
  "as.trace.note": { ar: "محاكاة. لا يوجد وكيل حقيقي بعد.", en: "Simulated. No real agent yet." },
  "as.conf": { ar: "درجة الثقة", en: "Confidence" },
  "as.conf.high": { ar: "عالية", en: "High" },
  "as.conf.low": { ar: "منخفضة", en: "Low" },
  "as.you": { ar: "أنت", en: "You" },
  "as.name": { ar: "المساعد", en: "Assistant" },
  "as.sellerlabel": { ar: "البائع", en: "Seller" },
    "as.history": { ar: "المحادثات السابقة", en: "Previous chats" },
  "as.new": { ar: "محادثة جديدة", en: "New chat" },
  "as.nohistory": { ar: "لا توجد محادثات محفوظة بعد.", en: "No saved chats yet." },
  "as.delete": { ar: "حذف المحادثة", en: "Delete chat" },
  "as.try": { ar: "جرّب أحد هذه الأسئلة", en: "Try one of these" },
  "as.next": { ar: "أسئلة مقترحة", en: "Suggested next" },
    "auth.login": { ar: "تسجيل الدخول", en: "Log in" },
  "auth.register": { ar: "إنشاء حساب", en: "Create account" },
  "auth.logout": { ar: "تسجيل الخروج", en: "Log out" },
  "auth.name": { ar: "الاسم الكامل", en: "Full name" },
  "auth.email": { ar: "البريد الإلكتروني", en: "Email" },
  "auth.phone": { ar: "رقم الهاتف", en: "Phone number" },
  "auth.phone.hint": { ar: "مثال: 01012345678", en: "Example: 01012345678" },
  "auth.password": { ar: "كلمة المرور", en: "Password" },
  "auth.password.hint": { ar: "8 أحرف على الأقل، وتحتوي على حروف وأرقام.", en: "At least 8 characters, with letters and digits." },
  "auth.noaccount": { ar: "ليس لديك حساب؟", en: "No account yet?" },
  "auth.haveaccount": { ar: "لديك حساب بالفعل؟", en: "Already have an account?" },
  "auth.loading": { ar: "جارٍ المعالجة", en: "Working" },
  "auth.mock": { ar: "وضع تجريبي: لا يوجد خادم، أي بيانات صحيحة تعمل.", en: "Demo mode: no server, any valid details work." },
  "auth.v.name": { ar: "أدخل اسمك الكامل.", en: "Enter your full name." },
  "auth.v.email": { ar: "أدخل بريدًا إلكترونيًا صحيحًا.", en: "Enter a valid email." },
  "auth.v.phone": { ar: "رقم الهاتف غير صحيح.", en: "Invalid phone number." },
  "auth.v.password": { ar: "كلمة المرور لا تطابق الشروط.", en: "Password does not meet the rules." },
  "auth.err.invalid_credentials": { ar: "البريد أو كلمة المرور غير صحيحة.", en: "Incorrect email or password." },
  "auth.err.email_taken": { ar: "هذا البريد مسجل بالفعل.", en: "This email is already registered." },
  "auth.err.role_not_allowed": { ar: "لا يمكن التسجيل بهذا النوع من الحسابات.", en: "This account type cannot self-register." },
  "auth.err.network": { ar: "تعذر الاتصال بالخادم.", en: "Could not reach the server." },
  "auth.err.generic": { ar: "حدث خطأ. حاول مرة أخرى.", en: "Something went wrong. Try again." },
    "cart.title": { ar: "سلة التسوق", en: "Shopping cart" },
  "cart.loading": { ar: "جارٍ التحميل", en: "Loading" },
  "cart.empty": { ar: "السلة فارغة", en: "Your cart is empty" },
  "cart.empty.hint": { ar: "أضف منتجات لتظهر هنا.", en: "Add products and they will show up here." },
  "cart.continue": { ar: "تصفح المنتجات", en: "Browse products" },
  "cart.unavailable": { ar: "غير متاح حاليًا، ولن يُحتسب في الإجمالي.", en: "Currently unavailable, not counted in the total." },
  "cart.removed": { ar: "هذا المنتج لم يعد موجودًا.", en: "This product no longer exists." },
  "cart.remove": { ar: "حذف", en: "Remove" },
  "cart.clear": { ar: "إفراغ السلة", en: "Clear cart" },
  "cart.qty": { ar: "الكمية", en: "Quantity" },
  "cart.maxstock": { ar: "وصلت إلى الحد الأقصى المتاح", en: "Maximum available reached" },
  "cart.summary": { ar: "ملخص الطلب", en: "Order summary" },
  "cart.subtotal": { ar: "المجموع الفرعي", en: "Subtotal" },
  "cart.shipping": { ar: "الشحن", en: "Shipping" },
  "cart.shipping.free": { ar: "مجاني", en: "Free" },
  "cart.total": { ar: "الإجمالي", en: "Total" },
  "cart.checkout": { ar: "إتمام الشراء", en: "Checkout" },
  "cart.checkout.login": { ar: "سجّل الدخول للمتابعة", en: "Log in to continue" },
  "cart.checkout.soon": { ar: "صفحة الدفع قيد البناء.", en: "The checkout page is being built." },
  // stock + prices (used by lib/format.ts; {n} is filled in by fill())
  "stock.out": { ar: "غير متوفر", en: "Out of stock" },
  "stock.left.one": { ar: "يتبقى قطعة واحدة", en: "Only 1 left" },
  "stock.left.many": { ar: "يتبقى {n} قطع", en: "Only {n} left" },
  "card.discount": { ar: "خصم {n}%", en: "{n}% off" },
  "products.count": { ar: "{n} منتج", en: "{n} products" },
  "cart.freeHint": {
    ar: "أضف {amount} من هذا البائع للحصول على شحن مجاني.",
    en: "Add {amount} from this seller for free shipping.",
  },
  // filters
  "filter.category": { ar: "الفئة", en: "Category" },
  "filter.all": { ar: "الكل", en: "All" },
  "filter.brand": { ar: "العلامة التجارية", en: "Brand" },
  "filter.price": { ar: "السعر (ج.م)", en: "Price (EGP)" },
  "filter.from": { ar: "من", en: "From" },
  "filter.to": { ar: "إلى", en: "To" },
  "filter.min": { ar: "أقل سعر", en: "Minimum price" },
  "filter.max": { ar: "أعلى سعر", en: "Maximum price" },
  "filter.inStock": { ar: "المتوفر في المخزون فقط", en: "In stock only" },
  "filter.clear": { ar: "مسح الفلاتر", en: "Clear filters" },
  // 404
  "notfound.title": { ar: "الصفحة غير موجودة", en: "Page not found" },
  "notfound.body": {
    ar: "قد يكون الرابط غير صحيح أو أن الصفحة لم تُنشأ بعد.",
    en: "The link may be wrong, or the page does not exist yet.",
  },
  "notfound.home": { ar: "العودة إلى الرئيسية", en: "Back to home" },
  "logo.home": { ar: "دكان تك - الصفحة الرئيسية", en: "Dokkan Tech - Home" },
  // product page
  "pd.back": { ar: "العودة إلى المنتجات", en: "Back to products" },
  "pd.notfound": { ar: "هذا المنتج غير موجود.", en: "This product does not exist." },
  "pd.error": { ar: "تعذر تحميل المنتج.", en: "Could not load the product." },
  "pd.unavailable": { ar: "غير متاح الآن", en: "Not available now" },
  "pd.qty": { ar: "الكمية", en: "Quantity" },
  "pd.added": { ar: "تمت الإضافة إلى السلة", en: "Added to cart" },
  "pd.description": { ar: "الوصف", en: "Description" },
  "pd.specs": { ar: "المواصفات", en: "Specifications" },
  "pd.similar": { ar: "منتجات مشابهة", en: "Similar products" },
  "pd.image": { ar: "صورة {n}", en: "Image {n}" },
  "pd.warranty": { ar: "ضمان {n} شهر", en: "{n}-month warranty" },
  "pd.warranty.none": { ar: "بدون ضمان", en: "No warranty" },
  "pd.returnable": { ar: "إرجاع خلال 14 يومًا", en: "14-day returns" },
  "pd.notReturnable": { ar: "غير قابل للإرجاع", en: "Not returnable" },
  "pd.delivery": { ar: "التوصيل خلال 3 أيام", en: "Delivery in 3 days" },
  "pd.freeShipping": { ar: "شحن مجاني من 5,000 ج.م", en: "Free shipping from EGP 5,000" },
  // reviews
  "rv.title": { ar: "التقييمات", en: "Reviews" },
  "rv.count": { ar: "{n} تقييم", en: "{n} reviews" },
  "rv.none": { ar: "لا توجد تقييمات بعد.", en: "No reviews yet." },
  "rv.verified": { ar: "شراء مؤكد", en: "Verified purchase" },
  "rv.stars": { ar: "{n} نجوم", en: "{n} stars" },
  // spec labels (keys match backend schemas/specs.py)
  "spec.ram_gb": { ar: "الرام", en: "RAM" },
  "spec.storage_gb": { ar: "التخزين", en: "Storage" },
  "spec.screen_inch": { ar: "الشاشة", en: "Screen" },
  "spec.battery_mah": { ar: "البطارية", en: "Battery" },
  "spec.camera_mp": { ar: "الكاميرا الرئيسية", en: "Main camera" },
  "spec.network": { ar: "الشبكة", en: "Network" },
  "spec.os": { ar: "نظام التشغيل", en: "Operating system" },
  "spec.color_ar": { ar: "اللون", en: "Color" },
  "spec.cpu": { ar: "المعالج", en: "Processor" },
  "spec.storage_type": { ar: "نوع التخزين", en: "Storage type" },
  "spec.gpu": { ar: "كارت الشاشة", en: "Graphics" },
  "spec.battery_hours": { ar: "عمر البطارية", en: "Battery life" },
  "spec.weight_kg": { ar: "الوزن", en: "Weight" },
  "spec.type": { ar: "النوع", en: "Type" },
  "spec.wireless": { ar: "لاسلكي", en: "Wireless" },
  "spec.noise_cancelling": { ar: "عزل الضوضاء", en: "Noise cancelling" },
  "spec.connector": { ar: "المنفذ", en: "Connector" },
  "spec.yes": { ar: "نعم", en: "Yes" },
  "spec.no": { ar: "لا", en: "No" },
  "spec.os.none": { ar: "بدون نظام", en: "None (FreeDOS)" },
  "spec.type.earbuds": { ar: "سماعات أذن", en: "Earbuds" },
  "spec.type.headphones": { ar: "سماعة رأس", en: "Headphones" },
  "spec.type.speaker": { ar: "مكبر صوت", en: "Speaker" },
  "spec.type.charger": { ar: "شاحن", en: "Charger" },
  "spec.type.power_bank": { ar: "باور بانك", en: "Power bank" },
  "spec.type.cable": { ar: "كابل", en: "Cable" },
  "unit.gb": { ar: "{n} جيجا", en: "{n} GB" },
  "unit.tb": { ar: "{n} تيرابايت", en: "{n} TB" },
  "unit.inch": { ar: "{n} بوصة", en: "{n}\"" },
  "unit.mah": { ar: "{n} مللي أمبير", en: "{n} mAh" },
  "unit.mp": { ar: "{n} ميجابكسل", en: "{n} MP" },
  "unit.hours": { ar: "{n} ساعة", en: "{n} hours" },
  "unit.kg": { ar: "{n} كجم", en: "{n} kg" },
} as const;

export type TKey = keyof typeof dict;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; toggle: () => void; t: (k: TKey) => string };

const I18nContext = createContext<Ctx | null>(null);
const STORAGE_KEY = "dalil.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "ar" || saved === "en") return saved;
  } catch {
    /* ignore */
  }
  return "ar";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  const t = useCallback((k: TKey) => dict[k][lang], [lang]);
  const toggle = useCallback(() => setLang((l) => (l === "ar" ? "en" : "ar")), []);

  const value = useMemo(() => ({ lang, setLang, toggle, t }), [lang, toggle, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
