"""Application configuration via pydantic-settings."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "PR Guardian"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/prguardian"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Auth
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # GitHub
    GITHUB_APP_ID: str | None = None
    GITHUB_APP_SLUG: str = "pr-guardian"  # the /apps/<slug> URL part
    GITHUB_APP_PRIVATE_KEY_PATH: str | None = None
    GITHUB_WEBHOOK_SECRET: str = "change-me-webhook-secret"
    GITHUB_TOKEN: str | None = None  # optional PAT fallback for the github client
    # GitHub OAuth
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Email OTP
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str = "PR Guardian"

    # Vector DB — pgvector only (embeddings stored in the KnowledgeChunk table
    # alongside the rest of the data; no separate service). EMBEDDING_DIM is set
    # in the LLM section below alongside the embedding model names.

    # LLM
    LLM_PROVIDER: Literal["ollama"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    # Dimensionality of the bge-m3 embedding model. pgvector stores vectors of exactly this width.
    EMBEDDING_DIM: int = 1024

    # RAG
    RAG_CHUNK_TOKENS: int = 512
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 8

    # Ingestion
    INGESTION_MAX_FILES: int = 5000
    INGESTION_MAX_FILE_BYTES: int = 512 * 1024  # skip files bigger than 512KB
    INGESTION_TEXT_EXTS: str = (
        ".py,.js,.ts,.tsx,.jsx,.go,.rs,.java,.kt,.rb,.php,.c,.cc,.cpp,.h,.hpp,"
        ".cs,.swift,.m,.mm,.scala,.clj,.ex,.exs,.erl,.hs,.ml,.lua,.pl,.r,.sh,"
        ".bash,.zsh,.fish,.ps1,.bat,.cmd,.yml,.yaml,.toml,.ini,.cfg,.conf,.json,"
        ".jsonc,.xml,.html,.css,.scss,.sass,.less,.vue,.svelte,.md,.rst,.txt,"
        ".sql,.graphql,.gql,.proto,.dockerfile,.env.example,.gitignore,.gitattributes"
    )

    # Pipeline
    SPAM_THRESHOLD: float = 0.75
    FLAG_BAN_THRESHOLD: int = 3
    MAX_PR_DIFF_BYTES: int = 500 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
