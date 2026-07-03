"""Agent schemas: create/update/read payloads."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LlmProviderLiteral = Literal["ollama", "gemini"]
VectorDbLiteral = Literal["pgvector", "chromadb"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_full_name: str = Field(
        min_length=3,
        max_length=255,
        description="GitHub repo in owner/name form, e.g. 'octocat/Hello-World'",
    )
    llm_provider: LlmProviderLiteral = "ollama"
    vector_db_type: VectorDbLiteral = "pgvector"
    github_installation_id: int | None = None

    @field_validator("repo_full_name")
    @classmethod
    def normalize_repo(cls, v: str) -> str:
        v = v.strip()
        # Accept a full URL, but store only owner/name.
        if "://" in v:
            # https://github.com/owner/name(.git)
            v = v.split("github.com/", 1)[-1]
        v = v.rstrip("/")
        if v.endswith(".git"):
            v = v[: -len(".git")]
        if v.count("/") != 1:
            raise ValueError("repo must be in 'owner/name' form")
        return v


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    llm_provider: LlmProviderLiteral | None = None
    vector_db_type: VectorDbLiteral | None = None
    github_installation_id: int | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    repo_full_name: str
    llm_provider: str
    vector_db_type: str
    github_installation_id: int | None
    is_active: bool
    ingestion_status: str
    last_ingested_at: datetime | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
