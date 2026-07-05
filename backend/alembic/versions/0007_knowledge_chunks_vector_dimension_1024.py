"""knowledge_chunks vector dimension 1024

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-05 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the entire table and recreate it with correct dimension
    op.execute("DROP TABLE IF EXISTS knowledge_chunks;")
    
    # Recreate the table with vector(1024)
    op.execute("""
        CREATE TABLE knowledge_chunks (
            id SERIAL PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            source_type VARCHAR(16) NOT NULL,
            source_ref VARCHAR(500) NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1024),
            token_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create index
    op.execute("CREATE INDEX ix_knowledge_chunks_agent_id ON knowledge_chunks(agent_id);")
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    # Drop the table
    op.execute("DROP TABLE IF EXISTS knowledge_chunks;")
    
    # Recreate with old dimension (768)
    op.execute("""
        CREATE TABLE knowledge_chunks (
            id SERIAL PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            source_type VARCHAR(16) NOT NULL,
            source_ref VARCHAR(500) NOT NULL,
            content TEXT NOT NULL,
            embedding vector(768),
            token_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    
    # Create index
    op.execute("CREATE INDEX ix_knowledge_chunks_agent_id ON knowledge_chunks(agent_id);")
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )
