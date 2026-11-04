"""add_pipeline_run_and_evidence_indexes

Revision ID: 89f8a221797c
Revises: 5850c3d9cfd4
Create Date: 2026-11-04 17:52:07.237743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89f8a221797c'
down_revision: Union[str, Sequence[str], None] = '5850c3d9cfd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: partial unique index on active pipeline runs, index on evidence records run+dimension, index on evidence sources evidence_id."""
    # 1. Partial unique index on pipeline_runs(investigation_id) WHERE status IN ('queued', 'running')
    op.create_index(
        'uq_pipeline_runs_active_investigation',
        'pipeline_runs',
        ['investigation_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    # 2. Index on evidence_records(pipeline_run_id, dimension)
    op.create_index(
        'ix_evidence_records_run_dimension',
        'evidence_records',
        ['pipeline_run_id', 'dimension'],
        unique=False,
    )

    # 3. Ensure index on evidence_sources(evidence_id) exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_evidence_sources_evidence_id ON evidence_sources (evidence_id)")


def downgrade() -> None:
    """Downgrade schema: drop evidence records run+dimension index and pipeline runs active unique index."""
    op.drop_index('ix_evidence_records_run_dimension', table_name='evidence_records')
    op.drop_index('uq_pipeline_runs_active_investigation', table_name='pipeline_runs')
