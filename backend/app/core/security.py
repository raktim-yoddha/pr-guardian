"""Security primitives: password hashing and JWT access tokens.

Uses ``bcrypt`` directly (no passlib). passlib is incompatible with modern
bcrypt releases and crashes on passwords longer than 72 bytes; calling bcrypt
directly is simpler and avoids both problems.
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = settings.JWT_ALGORITHM
_BCRYPT_MAX_BYTES = 72  # bcrypt hard limit


@lru_cache
def _fernet() -> Fernet:
    """Fernet keyed off SECRET_KEY — no separate secret to manage.

    ponytail: derives the 32-byte key from SECRET_KEY via SHA-256. Rotating
    SECRET_KEY invalidates stored ciphertexts (acceptable: keys are re-enterable).
    """
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a user-supplied secret (e.g. an LLM API key) for storage at rest."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str | None:
    """Decrypt a stored secret. Returns None if it can't be decrypted."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _truncate(password: str) -> bytes:
    """Encode to UTF-8 and cap at bcrypt's 72-byte limit."""
    raw = password.encode("utf-8")
    return raw[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a bcrypt hash of ``password`` (truncated to 72 bytes)."""
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if ``plain`` matches the bcrypt ``hashed`` string."""
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash → treat as a non-match, never raise.
        return False


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
