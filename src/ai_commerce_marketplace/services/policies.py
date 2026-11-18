import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.policy import Policy
from ai_commerce_marketplace.schemas.policy import PolicyOut, PolicySection, PolicySummaryOut

# Fixed display order for the policy pages.
ORDER = ("shipping", "returns", "warranty", "cancellation")

_SECTION = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$", re.MULTILINE)


def split_sections(body_md: str) -> list[PolicySection]:
    """Split a policy on its numbered headings (`## 1. title`).

    Pure function. The policy pages use it for a table of contents, and the Support Agent can use
    it to chunk policies for RAG (slug + section number + version).
    """
    matches = list(_SECTION.finditer(body_md))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_md)
        sections.append(
            PolicySection(
                no=int(m.group(1)),
                title=m.group(2),
                body=body_md[m.end() : end].strip(),
            )
        )
    return sections


def _summary(p: Policy) -> PolicySummaryOut:
    return PolicySummaryOut(
        slug=p.slug, category=p.category, title_ar=p.title_ar, version=p.version
    )


def list_policies(session: Session) -> list[PolicySummaryOut]:
    rows = session.scalars(select(Policy).where(Policy.is_current.is_(True))).all()
    rank = {slug: i for i, slug in enumerate(ORDER)}
    rows = sorted(rows, key=lambda p: (rank.get(p.slug, len(ORDER)), p.slug))
    return [_summary(p) for p in rows]


def get_policy(session: Session, slug: str) -> PolicyOut:
    """Current version of one policy, with its numbered sections."""
    p = session.scalar(select(Policy).where(Policy.slug == slug, Policy.is_current.is_(True)))
    if p is None:
        raise NotFoundError("Policy not found", code="policy_not_found")
    return PolicyOut(
        **_summary(p).model_dump(), body_md=p.body_md, sections=split_sections(p.body_md)
    )
