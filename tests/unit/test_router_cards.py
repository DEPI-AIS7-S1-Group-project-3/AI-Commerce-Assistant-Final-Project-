from ai_commerce_marketplace.agents.router.cards import pick_cards, short_name

TOOLS = {"search_products", "products_compare", "product_get"}


def p(i, title, brand):
    return {"id": i, "title_ar": title, "brand": brand, "price_egp": "1"}


HP_HG5 = p(1, "إتش بي HG5 لابتوب Core i5", "إتش بي")
HP_H7R = p(2, "إتش بي H7R لابتوب Ryzen 7", "إتش بي")
ASUS = p(3, "أسوس A5R لابتوب Ryzen 5", "أسوس")
LENOVO = p(4, "لينوفو L5R لابتوب Ryzen 5", "لينوفو")
JBL_H4 = p(5, "جي بي إل H4 سماعة رأس", "جي بي إل")
JBL_S2 = p(6, "جي بي إل S2 مكبر صوت", "جي بي إل")


def res(*products):
    return {"ok": True, "products": list(products)}


def test_short_name_is_brand_plus_model_even_for_multi_word_brands():
    assert short_name(HP_HG5) == "إتش بي HG5"
    assert short_name(JBL_H4) == "جي بي إل H4"


def test_cards_are_the_products_the_reply_recommends_in_mention_order():
    results = [
        ("search_products", res(LENOVO, ASUS)),  # an early search
        ("search_products", res(HP_HG5, HP_H7R, ASUS)),
    ]
    reply = "أرشح **أسوس A5R** للسعر، وبعده إتش بي HG5 للمونتاج."
    got = pick_cards(reply, results, TOOLS, fallback=[LENOVO])
    assert [c["id"] for c in got] == [3, 1]


def test_two_models_of_the_same_brand_are_not_mixed_up():
    reply = "سماعة جي بي إل H4 ممتازة."
    got = pick_cards(reply, [("search_products", res(JBL_H4, JBL_S2))], TOOLS, [])
    assert [c["id"] for c in got] == [5]


def test_when_the_reply_names_nothing_the_last_result_is_kept():
    reply = "ملقيتش حاجة مناسبة."
    got = pick_cards(reply, [("search_products", res(ASUS))], TOOLS, fallback=[LENOVO])
    assert got == [LENOVO]


def test_failed_tool_results_and_other_tools_are_ignored():
    results = [("search_products", {"ok": False}), ("policy_get", res(ASUS))]
    assert pick_cards("أسوس A5R", results, TOOLS, fallback=[]) == []
