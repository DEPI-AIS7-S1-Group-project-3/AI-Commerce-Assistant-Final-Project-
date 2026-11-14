from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.policy import PolicyOut, PolicySummaryOut
from ai_commerce_marketplace.services import policies as svc

# Public: the policy pages are readable without logging in.
router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicySummaryOut])
def list_policies(session: Session = Depends(get_session)):
    return svc.list_policies(session)


@router.get("/{slug}", response_model=PolicyOut)
def get_policy(slug: str, session: Session = Depends(get_session)):
    return svc.get_policy(session, slug)
