"""add_indicator_confidence_and_post_extractor_fields

Revision ID: 5850c3d9cfd4
Revises: 6d746b2de130
Create Date: 2026-11-04 17:03:32.375539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5850c3d9cfd4'
down_revision: Union[str, Sequence[str], None] = '6d746b2de130'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add confidence and details to extracted_indicators; add extractor fields to posts."""
    op.add_column(
        'extracted_indicators',
        sa.Column('confidence', sa.String(length=10), server_default='high', nullable=False)
    )
    op.create_check_constraint(
        'ck_extracted_indicators_confidence',
        'extracted_indicators',
        "confidence IN ('high', 'medium', 'low')"
    )
    op.add_column(
        'extracted_indicators',
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False)
    )

    op.add_column(
        'posts',
        sa.Column('extractor_version', sa.String(length=20), nullable=True)
    )
    op.add_column(
        'posts',
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema: drop extractor fields from posts; drop details, check constraint, and confidence from extracted_indicators."""
    op.drop_column('posts', 'extracted_at')
    op.drop_column('posts', 'extractor_version')

    op.drop_column('extracted_indicators', 'details')
    op.drop_constraint('ck_extracted_indicators_confidence', 'extracted_indicators', type_='check')
    op.drop_column('extracted_indicators', 'confidence')
