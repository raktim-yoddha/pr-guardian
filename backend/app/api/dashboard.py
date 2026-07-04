"""Dashboard endpoints: aggregate stats + flagged accounts (Phase 4).

All data is scoped to agents owned by the current user. Events are read-only
(immutable) — these endpoints only aggregate existing rows.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.models.agent import Agent
from app.models.github_account import GithubAccount
from app.models.pr_event import PREvent
from app.schemas.dashboard import (
    AgentStats,
    DashboardStats,
    FlaggedAccountRead,
)
from sqlalchemy import func, select

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _agent_ids_for_user(db: DBSession, user_id: int) -> list[int]:
    result = await db.execute(select(Agent.id).where(Agent.user_id == user_id))
    return [r for r in result.scalars().all()]


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    current_user: CurrentUser,
    db: DBSession,
    agent_id: int | None = Query(default=None, description="Scope to one agent"),
) -> DashboardStats:
    """Aggregate counts across the current user's agents (or one agent)."""
    base = select(PREvent).join(Agent, Agent.id == PREvent.agent_id).where(
        Agent.user_id == current_user.id
    )
    if agent_id is not None:
        base = base.where(PREvent.agent_id == agent_id)

    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    approved = int(
        await db.scalar(
            select(func.count())
            .select_from(base.subquery())
            .where(PREvent.decision == "approved")
        )
        or 0
    )
    declined = int(
        await db.scalar(
            select(func.count())
            .select_from(base.subquery())
            .where(PREvent.decision == "declined")
        )
        or 0
    )
    errors = int(
        await db.scalar(
            select(func.count())
            .select_from(base.subquery())
            .where(PREvent.decision == "error")
        )
        or 0
    )

    # Flagged accounts are those that appear as authors of declined events for
    # this user's agents. Banned = status "banned".
    author_subq = (
        select(PREvent.author_github.label("u"))
        .join(Agent, Agent.id == PREvent.agent_id)
        .where(Agent.user_id == current_user.id)
        .where(PREvent.decision == "declined")
        .distinct()
    ).subquery()
    if agent_id is not None:
        author_subq = (
            select(PREvent.author_github.label("u"))
            .where(PREvent.agent_id == agent_id)
            .where(PREvent.decision == "declined")
            .distinct()
        ).subquery()

    flagged = int(
        await db.scalar(select(func.count()).select_from(author_subq)) or 0
    )
    banned = int(
        await db.scalar(
            select(func.count(GithubAccount.id))
            .where(GithubAccount.github_username.in_(select(author_subq.c.u)))
            .where(GithubAccount.account_status == "banned")
        )
        or 0
    )

    approval_rate = (approved / total) if total else 0.0
    return DashboardStats(
        total_prs=total,
        approved=approved,
        declined=declined,
        errors=errors,
        flagged_accounts=flagged,
        banned_accounts=banned,
        approval_rate=round(approval_rate, 4),
    )


@router.get("/per-agent", response_model=list[AgentStats])
async def get_per_agent_stats(current_user: CurrentUser, db: DBSession) -> list[AgentStats]:
    """Stats broken down per agent for the current user."""
    result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.id).order_by(Agent.created_at.desc())
    )
    agents = list(result.scalars().all())
    out: list[AgentStats] = []
    for a in agents:
        total = int(
            await db.scalar(
                select(func.count(PREvent.id)).where(PREvent.agent_id == a.id)
            )
            or 0
        )
        approved = int(
            await db.scalar(
                select(func.count(PREvent.id))
                .where(PREvent.agent_id == a.id)
                .where(PREvent.decision == "approved")
            )
            or 0
        )
        declined = int(
            await db.scalar(
                select(func.count(PREvent.id))
                .where(PREvent.agent_id == a.id)
                .where(PREvent.decision == "declined")
            )
            or 0
        )
        out.append(
            AgentStats(
                agent_id=a.id,
                agent_name=a.name,
                repo_full_name=a.repo_full_name,
                total_prs=total,
                approved=approved,
                declined=declined,
                approval_rate=round((approved / total) if total else 0.0, 4),
            )
        )
    return out


@router.get("/flagged-accounts", response_model=list[FlaggedAccountRead])
async def list_flagged_accounts(
    current_user: CurrentUser,
    db: DBSession,
    agent_id: int | None = Query(default=None, description="Scope to one agent"),
) -> list[GithubAccount]:
    """GitHub accounts flagged by the current user's agents."""
    q = (
        select(PREvent.author_github.label("u"))
        .join(Agent, Agent.id == PREvent.agent_id)
        .where(Agent.user_id == current_user.id)
        .where(PREvent.decision == "declined")
        .distinct()
    )
    if agent_id is not None:
        q = (
            select(PREvent.author_github.label("u"))
            .where(PREvent.agent_id == agent_id)
            .where(PREvent.decision == "declined")
            .distinct()
        )
    names = [r for r in (await db.execute(q)).scalars().all()]
    if not names:
        return []
    result = await db.execute(
        select(GithubAccount)
        .where(GithubAccount.github_username.in_(names))
        .order_by(GithubAccount.flag_count.desc())
    )
    return list(result.scalars().all())


@router.post("/flagged-accounts/{github_username}/unflag", status_code=status.HTTP_200_OK)
async def unflag_account(
    github_username: str,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, str]:
    """Remove flags from a GitHub account (manual override)."""
    # Verify this account is associated with the user's agents
    q = (
        select(PREvent.author_github.label("u"))
        .join(Agent, Agent.id == PREvent.agent_id)
        .where(Agent.user_id == current_user.id)
        .where(PREvent.author_github == github_username)
        .distinct()
    )
    result = await db.execute(q)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found or not associated with your agents",
        )

    # Reset the account's flags
    account = await db.scalar(
        select(GithubAccount).where(GithubAccount.github_username == github_username)
    )
    if account:
        account.flag_count = 0
        account.account_status = "active"
        account.banned_at = None
        await db.commit()

    return {"message": f"Flags removed for {github_username}"}
