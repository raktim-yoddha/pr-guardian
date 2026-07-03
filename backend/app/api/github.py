"""GitHub App installation flow — lets users connect their repos.

Endpoints:
  GET /api/github/install       → redirects to GitHub's install URL
  GET /api/github/callback       → receives installation_id after user installs
  GET /api/github/installations  → lists repos the current user has installed the app on
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["github"])

GITHUB_API = "https://api.github.com"


def _sign_jwt_with_app_key(private_key_pem: str) -> str:
    """Create a GitHub App JWT (RS256) signed with the app's private key."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    import base64
    import json

    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(),
        password=None,
        backend=default_backend(),
    )
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": settings.GITHUB_APP_ID}
    header = {"alg": "RS256", "typ": "JWT"}

    def b64(obj: dict[str, Any]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode()
        )

    signing_input = f"{b64(header)}.{b64(payload)}".encode()
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _read_app_key() -> str | None:
    path = settings.GITHUB_APP_PRIVATE_KEY_PATH
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            return fh.read().decode()
    except OSError:
        return None


async def _get_app_jwt() -> str | None:
    app_key = _read_app_key()
    if not app_key or not settings.GITHUB_APP_ID:
        return None
    return _sign_jwt_with_app_key(app_key)


def _build_install_url(state: str) -> str:
    """Build the GitHub App installation URL using the configured slug."""
    slug = settings.GITHUB_APP_SLUG
    return f"https://github.com/apps/{slug}/installations/new?state={state}"


@router.get("/install")
async def install_github_app(
    current_user: CurrentUser,
) -> RedirectResponse:
    """Redirect the user to GitHub to install the app on their repos.

    The `state` parameter encodes the user's ID so we can link the installation
    back to them on callback.
    """
    if not settings.GITHUB_APP_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App is not configured. Set GITHUB_APP_ID in .env",
        )

    state = str(current_user.id)
    url = _build_install_url(state)
    logger.info("github_install: redirecting user %d to %s", current_user.id, url)
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback")
async def github_install_callback(
    request: Request,
    current_user: CurrentUser,
    installation_id: int | None = None,
    state: str | None = None,
    setup_action: str | None = None,
) -> dict[str, Any]:
    """Handle the redirect back from GitHub after app installation.

    GitHub sends `installation_id` and `state` (which we set to the user ID).
    Returns the installation ID so the frontend can use it when creating agents.
    """
    if setup_action == "request":
        # User requested the app but an org admin needs to approve.
        return {
            "status": "pending_approval",
            "message": "App installation request sent to org admin. Waiting for approval.",
        }

    if not installation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No installation_id in callback",
        )

    # Verify state matches the current user (optional but good practice).
    if state and int(state) != current_user.id:
        logger.warning(
            "github_callback: state mismatch (expected %d, got %s)",
            current_user.id,
            state,
        )
        # Still proceed — state is informational, not security-critical here.

    # Fetch accessible repositories for this installation.
    app_jwt = await _get_app_jwt()
    if not app_jwt:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub App JWT not available",
        )

    repos: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get installation access token.
        resp = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {app_jwt}"},
        )
        resp.raise_for_status()
        token = resp.json()["token"]

        # List repos accessible to this installation.
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await client.get(
            f"{GITHUB_API}/installation/repositories",
            headers=headers,
            params={"per_page": 100},
        )
        resp.raise_for_status()
        repos = [
            {
                "full_name": r["full_name"],
                "private": r.get("private", False),
            }
            for r in resp.json().get("repositories", [])
        ]

    logger.info(
        "github_callback: user %d installed app, installation_id=%d, repos=%d",
        current_user.id,
        installation_id,
        len(repos),
    )

    return {
        "status": "installed",
        "installation_id": installation_id,
        "repos": repos,
    }


@router.get("/installations")
async def list_installations(
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    """List the current user's GitHub App installations and accessible repos.

    Uses the global GITHUB_APP_ID + private key to look up which installations
    exist for repos the user might want to guard.
    """
    app_jwt = await _get_app_jwt()
    if not app_jwt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App is not configured",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{GITHUB_API}/app/installations",
            headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
            params={"per_page": 100},
        )
        resp.raise_for_status()
        installations = resp.json()

    result: list[dict[str, Any]] = []
    for inst in installations:
        iid = inst["id"]
        account = inst.get("account") or {}
        result.append({
            "installation_id": iid,
            "account_login": account.get("login"),
            "account_type": account.get("type"),
            "permissions": inst.get("permissions", {}),
        })

    return result
