"""Google OAuth API endpoints for authentication."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter()

GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/google/oauth/authorize")
async def google_oauth_authorize(request: Request):
    """Generate Google OAuth authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    redirect_uri = f"{request.url_for('google_oauth_callback')}"
    scope = "openid email profile"
    
    auth_url = (
        f"{GOOGLE_OAUTH_URL}"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&response_type=code"
        f"&access_type=offline"
    )
    
    return {"authorization_url": auth_url}


@router.get("/google/oauth/callback")
async def google_oauth_callback(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback and create/login user."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{request.url_for('google_oauth_callback')}",
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")
    
    # Fetch user info from Google
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        google_user = user_resp.json()
    
    # Check if user exists by email
    from sqlalchemy import select
    from app.core.security import get_password_hash
    
    result = await db.execute(
        select(User).where(User.email == google_user["email"])
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user
        user = User(
            email=google_user["email"],
            hashed_password=get_password_hash("oauth_user"),  # Placeholder password
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # Generate JWT token
    access_token_jwt = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token_jwt,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
        }
    }
