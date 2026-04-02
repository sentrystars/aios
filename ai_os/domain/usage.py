from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UsageTaskSummary(BaseModel):
    id: str
    objective: str
    status: str
    runtime_name: str | None = None
    updated_at: datetime
