from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReminderRecord(BaseModel):
    id: str
    title: str
    note: str = ""
    due_hint: str = "unspecified"
    scheduled_for: datetime
    source_task_id: str | None = None
    origin: str | None = None
    last_seen_at: datetime | None = None


class CalendarEventRecord(BaseModel):
    id: str
    title: str
    note: str = ""
    due_hint: str = "unspecified"
    scheduled_for: datetime
    duration_minutes: int = Field(default=30, ge=1, le=1440)
    source_task_id: str | None = None
    origin: str | None = None
    last_seen_at: datetime | None = None
