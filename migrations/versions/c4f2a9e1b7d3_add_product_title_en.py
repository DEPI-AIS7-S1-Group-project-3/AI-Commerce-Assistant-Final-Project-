"""add products.title_en (optional English title)

Revision ID: c4f2a9e1b7d3
Revises: 92d19afd42b8
Create Date: 2026-11-16 17:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4f2a9e1b7d3'
down_revision: Union[str, Sequence[str], None] = '92d19afd42b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Optional English title. NULL = show the Arabic title instead."""
    op.add_column('products', sa.Column('title_en', sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f('ck_products_title_en_not_blank'),
        'products',
        'title_en IS NULL OR length(btrim(title_en)) > 0',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_products_title_en_not_blank'), 'products', type_='check')
    op.drop_column('products', 'title_en')
