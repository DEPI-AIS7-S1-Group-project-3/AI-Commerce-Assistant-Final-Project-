import pytest

from ai_commerce_marketplace.nlp.arabic import build_search_text, normalize_ar


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("مُحَمَّد", "محمد"),  # التشكيل
        ("جـــوال", "جوال"),  # التطويل
        ("أحمد إبراهيم آمنة", "احمد ابراهيم امنه"),  # الألف + التاء المربوطة
        ("مستشفى", "مستشفي"),  # الألف المقصورة
        ("سماعة", "سماعه"),
        ("١٢٨ جيجا", "128 جيجا"),  # أرقام عربية
        ("  iPhone   15 PRO ", "iphone 15 pro"),  # مسافات وحروف كبيرة
        ("سماعة (بلوتوث)، أسود!", "سماعه بلوتوث اسود"),  # علامات الترقيم
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_ar(raw, expected):
    assert normalize_ar(raw) == expected


@pytest.mark.parametrize("text", ["سماعة بلوتوث أسود", "مُوبايل Samsung ١٢٨", "  "])
def test_normalize_is_idempotent(text):
    assert normalize_ar(normalize_ar(text)) == normalize_ar(text)


def test_query_matches_product_after_normalizing():
    product = normalize_ar("سماعة بلوتوث")
    assert normalize_ar("سماعه") in product


def test_build_search_text():
    assert (
        build_search_text("سلسلة A تجريبية 128 جيجا", "Samsung", "موبايل ممتاز")
        == "سلسله a تجريبيه 128 جيجا samsung موبايل ممتاز"
    )


def test_build_search_text_skips_empty_parts():
    assert build_search_text("سماعة", None, "") == "سماعه"
