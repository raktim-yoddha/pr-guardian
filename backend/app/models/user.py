"""User model — registered PR Guardian accounts."""
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Bring-your-own LLM config. Chosen chat provider ("groq" | "gemini" |
    # "ollama"); NULL → fall back to the server's env-default provider + key.
    preferred_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Per-provider API keys, Fernet-encrypted, stored as JSON: {"groq": "<enc>"}.
    encrypted_api_keys: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional custom Ollama endpoint for the "ollama" provider.
    ollama_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="user", cascade="all, delete-orphan"
    )
    github_connections: Mapped[list["GitHubConnection"]] = relationship(
        "GitHubConnection", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
