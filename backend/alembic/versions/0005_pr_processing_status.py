"""Add PRProcessingStatus model for real-time PR processing tracking.

Revision ID: 0005_pr_processing_status
Revises: 0004_github_connections
Create Date: 2024-01-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pr_processing_status table
    op.create_table(
        'pr_processing_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('pr_url', sa.String(length=500), nullable=False),
        sa.Column('pr_title', sa.String(length=500), nullable=False),
        sa.Column('author_github', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='detected'),
        sa.Column('layer_results', postgresql.JSON(), nullable=True),
        sa.Column('final_decision', sa.String(length=16), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pr_processing_status_agent_id'), 'pr_processing_status', ['agent_id'], unique=False)
    op.create_index(op.f('ix_pr_processing_status_status'), 'pr_processing_status', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_pr_processing_status_status'), table_name='pr_processing_status')
    op.drop_index(op.f('ix_pr_processing_status_agent_id'), table_name='pr_processing_status')
    
    # Drop table
    op.drop_table('pr_processing_status')
    
    # Drop enum type
    processing_status_enum = postgresql.ENUM(
        'detected', 'queued', 'spam_check', 'malicious_code_check',
        'prompt_injection_check', 'summary_generation', 'completed', 'failed',
        name='processing_status'
    )
    processing_status_enum.drop(op.get_bind())
