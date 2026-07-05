"""Ingestion log model — tracks step-by-step progress of repo ingestion."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Step identifier (e.g., "reset_vector_store", "fetch_repo_files", "fetch_issues", "store_chunks")
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Human-readable message
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Progress info
    current: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Current item count
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)    # Total items
    
    # Status of this step
    status: Mapped[str] = mapped_column(String(16), default="info", nullable=False)  # info, success, error, warning
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    def __repr__(self) -> str:
        return f"<IngestionLog id={self.id} agent_id={self.agent_id} step={self.step}>"
