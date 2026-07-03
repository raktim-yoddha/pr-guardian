"""GitHub OAuth API endpoints for account connection."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.github_connection import GitHubConnection
from app.models.user import User

router = APIRouter()

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


@router.get("/github/oauth/authorize")
async def github_oauth_authorize(request: Request):
    """Generate GitHub OAuth authorization URL."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    redirect_uri = f"{request.url_for('github_oauth_callback')}"
    scope = "repo admin:org admin:public_key admin:repo_hook user"
    
    auth_url = (
        f"{GITHUB_OAUTH_URL}"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    
    return {"authorization_url": auth_url}


@router.get("/github/oauth/callback")
async def github_oauth_callback(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback - login or connect account."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")
    
    # Fetch user info from GitHub
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            f"{GITHUB_API_URL}/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        github_user = user_resp.json()
    
    # Check if user exists by GitHub ID
    from sqlalchemy import select
    from app.core.security import get_password_hash
    
    result = await db.execute(
        select(User).where(User.email == github_user.get("email"))
    )
    user = result.scalar_one_or_none()
    
    # Create user if doesn't exist
    if not user:
        user = User(
            email=github_user.get("email") or f"{github_user['login']}@github.local",
            hashed_password=get_password_hash("github_oauth"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # Check if connection already exists
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.user_id == user.id,
            GitHubConnection.github_user_id == github_user["id"],
        )
    )
    existing_connection = result.scalar_one_or_none()
    
    if existing_connection:
        # Update existing connection
        existing_connection.access_token = access_token
        existing_connection.github_username = github_user["login"]
        existing_connection.github_email = github_user.get("email")
        existing_connection.status = "active"
    else:
        # Create new connection
        connection = GitHubConnection(
            user_id=user.id,
            github_user_id=github_user["id"],
            github_username=github_user["login"],
            github_email=github_user.get("email"),
            access_token=access_token,
            status="active",
        )
        db.add(connection)
    
    await db.commit()
    
    # Generate JWT token for auto-login
    from app.core.security import create_access_token
    jwt_token = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
        },
        "github_connected": True,
    }


@router.get("/github/connections")
async def list_github_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all GitHub connections for the current user."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    )
    connections = result.scalars().all()
    
    return [
        {
            "id": conn.id,
            "github_username": conn.github_username,
            "github_email": conn.github_email,
            "status": conn.status,
            "created_at": conn.created_at,
        }
        for conn in connections
    ]


@router.delete("/github/connections/{connection_id}")
async def delete_github_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a GitHub connection."""
    from sqlalchemy import select, delete
    
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    await db.execute(delete(GitHubConnection).where(GitHubConnection.id == connection_id))
    await db.commit()
    
    return {"message": "Connection deleted successfully"}


@router.get("/github/connections/{connection_id}/repos")
async def list_github_repos(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List repositories accessible through a GitHub connection."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Fetch repositories from GitHub
    async with httpx.AsyncClient() as client:
        repos_resp = await client.get(
            f"{GITHUB_API_URL}/user/repos",
            headers={
                "Authorization": f"Bearer {connection.access_token}",
                "Accept": "application/vnd.github+json",
            },
            params={"per_page": 100, "sort": "updated"},
        )
        repos_resp.raise_for_status()
        repos = repos_resp.json()
    
    return [
        {
            "full_name": repo["full_name"],
            "name": repo["name"],
            "owner": repo["owner"]["login"],
            "description": repo.get("description"),
            "private": repo["private"],
            "updated_at": repo["updated_at"],
        }
        for repo in repos
    ]
