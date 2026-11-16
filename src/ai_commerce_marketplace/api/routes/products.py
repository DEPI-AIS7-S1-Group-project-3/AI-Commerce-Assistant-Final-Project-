from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.catalog import ProductOut
from ai_commerce_marketplace.services import catalog as svc

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: Session = Depends(get_session)):
    """Public product page data. No login needed."""
    return svc.get_product(session, product_id)
