"""PREvent model — immutable audit log of every PR decision the pipeline makes."""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PREvent(Base):
    __tablename__ = "pr_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_url: Mapped[str] = mapped_column(String(500), nullable=False)
    author_github: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # "approved" | "declined" | "error"
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # Which layer caught it. Null for approvals. One of:
    # "spam" | "malicious_code" | "prompt_injection" | "summary"
    layer_caught: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<PREvent pr={self.pr_number} decision={self.decision} "
            f"layer={self.layer_caught}>"
        )
