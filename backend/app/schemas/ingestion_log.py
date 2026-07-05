"""Ingestion log schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    step: str
    message: str
    current: int | None
    total: int | None
    status: str
    created_at: datetime
