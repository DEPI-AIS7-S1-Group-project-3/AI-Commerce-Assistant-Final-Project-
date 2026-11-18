"""Read-only catalog search service used by the Shopping Agent tools."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.models import Brand, Category


def list_categories_brands(session: Session) -> dict[str, list[dict[str, Any]]]:
    """All categories and brands, so the agent can turn words into filters (slugs)."""
    categories = session.execute(
        select(
            Category.id,
            Category.slug,
            Category.name_ar,
            Category.name_en,
            Category.parent_id,
            Category.spec_kind,
        ).order_by(Category.sort_order, Category.id)
    ).mappings()
    brands = session.execute(
        select(Brand.slug, Brand.name, Brand.name_ar).order_by(Brand.name)
    ).mappings()
    return {
        "categories": [dict(row) for row in categories],
        "brands": [dict(row) for row in brands],
    }
