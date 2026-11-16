from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.catalog import ProductOut
from ai_commerce_marketplace.services import catalog as svc
from ai_commerce_marketplace.services.catalog import ProductSort

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    q: Annotated[str | None, Query(max_length=100, description="Search text (AR or EN)")] = None,
    category: Annotated[str | None, Query(description="Category slug")] = None,
    brand: Annotated[str | None, Query(description="Brand slug")] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    in_stock: bool = False,
    sort: ProductSort = "newest",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
):
    """Public product listing. Inactive products are never included.

    A parent category slug also matches products in its sub-categories.
    """
    return svc.list_products(
        session,
        q=q,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: Session = Depends(get_session)):
    """Public product page data. No login needed."""
    return svc.get_product(session, product_id)
