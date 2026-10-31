import re
import unicodedata

# التشكيل: فتحة، ضمة، كسرة، شدة، سكون... + الألف الخنجرية
_DIACRITICS = re.compile("[\u064b-\u065f\u0670]")

_TRANSLATION = str.maketrans(
    {
        # أشكال الألف كلها -> ا
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",  # الألف المقصورة -> ياء
        "ة": "ه",  # التاء المربوطة -> هاء
        "ؤ": "و",
        "ئ": "ي",
        "\u0640": None,  # التطويل (ـ) بيتشال
        # الأرقام العربية والفارسية -> 0-9
        **{chr(0x0660 + i): str(i) for i in range(10)},
        **{chr(0x06F0 + i): str(i) for i in range(10)},
    }
)

_NON_WORD = re.compile(r"[\W_]+")


def normalize_ar(text: str | None) -> str:
    """يوحّد النص العربي عشان البحث يشتغل: نفس الدالة تتطبق على المنتجات وعلى كلام العميل."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text)
    text = text.translate(_TRANSLATION)
    text = text.lower()
    return _NON_WORD.sub(" ", text).strip()


def build_search_text(*parts: str | None) -> str:
    """يبني عمود products.search_text من (العنوان + الماركة + الوصف)."""
    return normalize_ar(" ".join(p for p in parts if p))
