"""PRProcessingStatus model — tracks real-time processing state of PRs through layers."""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PRProcessingStatus(Base):
    """Tracks the real-time status of a PR being processed through the pipeline layers."""
    __tablename__ = "pr_processing_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_url: Mapped[str] = mapped_column(String(500), nullable=False)
    pr_title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_github: Mapped[str] = mapped_column(String(255), nullable=False)

    # Current processing status
    status: Mapped[str] = mapped_column(
        String(32),
        default="detected",
        nullable=False,
        index=True
    )

    # Layer-by-layer results (JSON)
    layer_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Final decision (filled when complete)
    final_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["Agent"] = relationship("Agent")

    def __repr__(self) -> str:
        return (
            f"<PRProcessingStatus pr={self.pr_number} "
            f"status={self.status} decision={self.final_decision}>"
        )
