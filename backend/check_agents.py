"""Check agent installation IDs in the database."""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from sqlalchemy import select


async def check_agents():
    """Print all agents with their installation IDs."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent))
        agents = result.scalars().all()
        
        if not agents:
            print("No agents found in database.")
            return
        
        print(f"Found {len(agents)} agent(s):\n")
        for agent in agents:
            print(f"ID: {agent.id}")
            print(f"Name: {agent.name}")
            print(f"Repo: {agent.repo_full_name}")
            print(f"Installation ID: {agent.github_installation_id}")
            print(f"Active: {agent.is_active}")
            print(f"Ingestion Status: {agent.ingestion_status}")
            print(f"LLM Provider: {agent.llm_provider}")
            print("-" * 40)


if __name__ == "__main__":
    asyncio.run(check_agents())
