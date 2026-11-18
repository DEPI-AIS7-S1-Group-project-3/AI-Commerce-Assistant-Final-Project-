from decimal import Decimal

from ai_commerce_marketplace.agents.seller.schemas import MetricChange, SalesSummary


def test_decimals_become_strings_in_json():
    s = SalesSummary(
        date_from="2026-10-01",
        date_to="2026-10-31",
        revenue=Decimal("200.00"),
        units_sold=2,
        orders_count=1,
        aov=Decimal("200.00"),
    )
    assert s.model_dump(mode="json")["revenue"] == "200.00"


def test_change_pct_can_be_null():
    m = MetricChange(a=Decimal("0"), b=Decimal("5"), delta=Decimal("5"))
    assert m.model_dump(mode="json")["change_pct"] is None
