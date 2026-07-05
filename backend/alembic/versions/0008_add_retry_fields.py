"""add retry fields to pr_processing_status and fix stuck PRs

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-05 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retry fields
    op.add_column('pr_processing_status', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pr_processing_status', sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True))
    
    # Fix stuck PRs - update any "detected" status to "queued"
    op.execute("""
        UPDATE pr_processing_status 
        SET status = 'queued', queued_at = NOW() 
        WHERE status = 'detected'
    """)
    
    # Also update any PRs that are stuck without queued_at
    op.execute("""
        UPDATE pr_processing_status 
        SET queued_at = NOW() 
        WHERE status = 'queued' AND queued_at IS NULL
    """)


def downgrade() -> None:
    op.drop_column('pr_processing_status', 'last_retry_at')
    op.drop_column('pr_processing_status', 'retry_count')
