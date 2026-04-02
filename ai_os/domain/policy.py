from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PolicyRuleDescriptor(BaseModel):
    name: str
    hook: str
    allowed: bool
    terminal: bool = False
    reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
