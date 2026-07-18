"""Application configuration via pydantic-settings."""
import json
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_db_url(url: str) -> str:
    """Coerce a Postgres URL to the async asyncpg driver and drop libpq-only params.

    Managed providers (Neon, Render, Supabase) hand out ``postgresql://…?sslmode=require``
    which SQLAlchemy routes to the *sync* psycopg2 driver, and asyncpg rejects the
    ``sslmode`` / ``channel_binding`` query params. Rewrite the scheme to
    ``postgresql+asyncpg`` and strip those params so pasting the raw string works.
    """
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"):
        scheme = "postgresql+asyncpg"
    if scheme != "postgresql+asyncpg":
        return url  # sqlite / already-custom driver → leave as-is
    keep = [
        kv for kv in parts.query.split("&")
        if kv and kv.split("=", 1)[0] not in ("sslmode", "channel_binding")
    ]
    return urlunsplit((scheme, parts.netloc, parts.path, "&".join(keep), parts.fragment))


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

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            # Try JSON array first
            if v.startswith("["):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            # Fallback: split by comma
            return [origin.strip().strip('"').strip("'") for origin in v.split(",") if origin.strip()]
        return ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/prguardian"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def _fix_db_url(cls, v: str) -> str:
        return _normalize_db_url(v)

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    # Worker-specific pool settings (separate from main app)
    WORKER_DB_POOL_SIZE: int = 2
    WORKER_DB_MAX_OVERFLOW: int = 5

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
    GITHUB_REDIRECT_URI: str = "http://localhost:3000/oauth/callback?provider=github"
    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/oauth/callback?provider=google"

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

    # LLM — chat provider. Default groq (free, fast). Per-user override + BYO
    # key lives on the User row; env keys below are the shared fallback.
    LLM_PROVIDER: Literal["groq", "gemini", "ollama"] = "groq"

    # Groq (OpenAI-compatible REST)
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Google Gemini (generativelanguage REST)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Ollama (local, opt-in)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Embeddings — local CPU model via fastembed (ONNX, no external service, no
    # key). bge-small-en-v1.5 = 384 dims; pgvector column width must match.
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384

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
