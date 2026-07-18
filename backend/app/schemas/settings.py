"""User settings schemas — LLM provider + bring-your-own API keys."""
from typing import Literal

from pydantic import BaseModel, Field

ProviderLiteral = Literal["groq", "gemini", "ollama"]


class SettingsRead(BaseModel):
    preferred_provider: str | None
    ollama_base_url: str | None
    # Which providers have a key stored (never the keys themselves).
    configured_providers: list[str]
    # The server's env-default provider, used when preferred_provider is unset.
    default_provider: str


class SettingsUpdate(BaseModel):
    preferred_provider: ProviderLiteral | None = None
    ollama_base_url: str | None = Field(default=None, max_length=255)
    # Plaintext keys to store (encrypted). Empty string clears that provider's key.
    api_keys: dict[ProviderLiteral, str] | None = None
