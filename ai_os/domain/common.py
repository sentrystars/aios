from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventRecord(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class TimelineItem(BaseModel):
    timestamp: datetime
    phase: str
    title: str
    detail: str
    event_type: str
