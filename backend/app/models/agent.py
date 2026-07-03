"""Agent model — a guardbot tied to one GitHub repo and one user."""
from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

LLMProvider = Literal["ollama", "gemini"]
VectorDBType = Literal["pgvector", "chromadb"]
IngestionStatus = Literal["pending", "running", "done", "failed"]


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    repo_full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # e.g. "octocat/Hello-World"

    llm_provider: Mapped[str] = mapped_column(String(16), nullable=False, default="ollama")
    vector_db_type: Mapped[str] = mapped_column(String(16), nullable=False, default="pgvector")

    github_installation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Phase 2 will populate these; defined now so the schema is stable.
    ingestion_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="agents")
    events: Mapped[list["PREvent"]] = relationship(
        "PREvent", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} repo={self.repo_full_name!r} active={self.is_active}>"
