"""add_unique_index_lower_marketplaces_name

Revision ID: 6d746b2de130
Revises: ee79a6dc2f27
Create Date: 2026-11-04 16:18:15.912659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d746b2de130'
down_revision: Union[str, Sequence[str], None] = 'ee79a6dc2f27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: unique index on lower(marketplaces.name)."""
    op.create_index(
        'uq_marketplaces_lower_name',
        'marketplaces',
        [sa.text('lower(name)')],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_marketplaces_lower_name', table_name='marketplaces')
