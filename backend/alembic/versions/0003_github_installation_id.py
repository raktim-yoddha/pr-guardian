"""add github_installation_id to agents

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("github_installation_id", sa.Integer(), nullable=True))
    op.create_index("ix_agents_github_installation_id", "agents", ["github_installation_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_github_installation_id", table_name="agents")
    op.drop_column("agents", "github_installation_id")
