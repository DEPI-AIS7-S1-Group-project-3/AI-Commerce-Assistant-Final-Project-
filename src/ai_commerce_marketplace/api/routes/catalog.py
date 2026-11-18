from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.catalog import BrandOut, CategoryOut
from ai_commerce_marketplace.services import catalog as svc

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_session)):
    """Leaf categories (the ones products belong to), in display order. Public."""
    return svc.list_categories(session)


@router.get("/brands", response_model=list[BrandOut])
def list_brands(session: Session = Depends(get_session)):
    """All brands, by name. Public."""
    return svc.list_brands(session)
