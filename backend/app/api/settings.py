"""User settings: LLM provider selection + bring-your-own API keys.

Keys are Fernet-encrypted at rest and never returned to the client — the read
endpoint only reports which providers have a key configured.
"""
import json

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings as app_settings
from app.core.security import encrypt_secret
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _configured_providers(user) -> list[str]:
    if not user.encrypted_api_keys:
        return []
    try:
        return [p for p, v in json.loads(user.encrypted_api_keys).items() if v]
    except (ValueError, TypeError):
        return []


@router.get("", response_model=SettingsRead)
async def get_settings(current_user: CurrentUser) -> SettingsRead:
    return SettingsRead(
        preferred_provider=current_user.preferred_provider,
        ollama_base_url=current_user.ollama_base_url,
        configured_providers=_configured_providers(current_user),
        default_provider=app_settings.LLM_PROVIDER,
    )


@router.put("", response_model=SettingsRead)
async def update_settings(
    payload: SettingsUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> SettingsRead:
    if payload.preferred_provider is not None:
        current_user.preferred_provider = payload.preferred_provider
    if payload.ollama_base_url is not None:
        current_user.ollama_base_url = payload.ollama_base_url or None

    if payload.api_keys is not None:
        try:
            keys: dict = json.loads(current_user.encrypted_api_keys) if current_user.encrypted_api_keys else {}
        except (ValueError, TypeError):
            keys = {}
        for provider, plaintext in payload.api_keys.items():
            if plaintext:
                keys[provider] = encrypt_secret(plaintext)
            else:
                keys.pop(provider, None)  # empty string clears the key
        current_user.encrypted_api_keys = json.dumps(keys) if keys else None

    await db.commit()
    await db.refresh(current_user)
    return SettingsRead(
        preferred_provider=current_user.preferred_provider,
        ollama_base_url=current_user.ollama_base_url,
        configured_providers=_configured_providers(current_user),
        default_provider=app_settings.LLM_PROVIDER,
    )
