import pytest

from ai_commerce_marketplace.services.policy_search import (
    SectionDoc,
    rank_sections,
    tokens,
    word_similarity,
)


def doc(slug, no, title, body, policy_title="سياسة"):
    return SectionDoc(slug, policy_title, "2026-10-01", no, title, body)


DOCS = [
    doc("returns", 1, "مهلة الإرجاع", "ترجع المنتج خلال 14 يوم من التسليم.", "سياسة الإرجاع"),
    doc(
        "returns",
        3,
        "منتجات غير قابلة للإرجاع",
        "السماعات الداخلية لا ترجع لأسباب صحية.",
        "سياسة الإرجاع",
    ),
    doc("shipping", 3, "رسوم الشحن", "الشحن مجاني للطلبات فوق 1000 جنيه.", "سياسة الشحن"),
    doc("warranty", 1, "مدة الضمان", "الضمان من تاريخ التسليم.", "سياسة الضمان"),
]


def top(query):
    hits = rank_sections(query, DOCS)
    return [(h.doc.slug, h.doc.no) for h in hits]


def test_tokens_drop_stopwords_and_definite_article():
    assert tokens("هل الشحن مجاني؟") == ["شحن", "مجاني"]


def test_similarity_same_root_with_different_vowels():
    assert word_similarity("ارجع", "ارجاع") >= 0.7
    assert word_similarity("بترجع", "ارجاع") >= 0.7


def test_similarity_unrelated_words_do_not_match():
    assert word_similarity("شحن", "ضمان") < 0.7


def test_finds_the_section_by_topic():
    assert top("الشحن بكام؟")[0] == ("shipping", 3)
    assert top("الضمان بيبدأ امتى")[0] == ("warranty", 1)


def test_colloquial_verb_matches_the_policy_noun():
    assert top("عايز ارجع المنتج")[0][0] == "returns"


def test_specific_section_beats_general_one():
    assert top("اقدر ارجع السماعة الداخلية؟")[0] == ("returns", 3)


def test_price_word_means_fee():
    # "الشحن بكام؟" must reach the shipping fee section, not any section that mentions shipping
    docs = [
        doc("cancellation", 1, "الإلغاء قبل الشحن", "تقدر تلغي قبل الشحن بدون رسوم إضافية."),
        *DOCS,
    ]
    hits = rank_sections("الشحن بكام؟", docs)
    assert (hits[0].doc.slug, hits[0].doc.no) == ("shipping", 3)


def test_how_many_days_means_delivery_duration():
    docs = [
        doc("shipping", 2, "مدة التوصيل", "خلال يومين من تاريخ إنشاء الطلب."),
        doc("shipping", 7, "تأخر التوصيل", "لو الطلب اتأخر تواصل مع البائع بخصوص الشحن."),
        *DOCS,
    ]
    assert top_of("الشحن بياخد كام يوم؟", docs) == ("shipping", 2)


def top_of(query, docs):
    hit = rank_sections(query, docs)[0]
    return hit.doc.slug, hit.doc.no


def test_unrelated_question_has_no_hits():
    assert rank_sections("مين رئيس الجمهورية", DOCS) == []


def test_empty_or_stopword_only_query_has_no_hits():
    assert rank_sections("", DOCS) == []
    assert rank_sections("هل ما في", DOCS) == []


def test_no_documents_has_no_hits():
    assert rank_sections("الشحن", []) == []


def test_order_is_best_first_and_stable():
    hits = rank_sections("الشحن مجاني", DOCS)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("query", ["Return policy?", "how long is the warranty"])
def test_latin_questions_do_not_crash(query):
    assert isinstance(rank_sections(query, DOCS), list)
