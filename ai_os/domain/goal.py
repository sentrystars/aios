from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .common import utc_now
from .task import TaskRecord


class GoalStatus(str, Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    DONE = "done"
    ARCHIVED = "archived"


class GoalKind(str, Enum):
    NORTH_STAR = "north_star"
    INITIATIVE = "initiative"
    PROJECT = "project"


class GoalRecord(BaseModel):
    id: str
    title: str
    kind: GoalKind = GoalKind.PROJECT
    status: GoalStatus = GoalStatus.ACTIVE
    horizon: str = "current"
    summary: str = ""
    success_metrics: list[str] = Field(default_factory=list)
    parent_goal_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GoalCreatePayload(BaseModel):
    title: str
    kind: GoalKind = GoalKind.PROJECT
    status: GoalStatus = GoalStatus.ACTIVE
    horizon: str = "current"
    summary: str = ""
    success_metrics: list[str] = Field(default_factory=list)
    parent_goal_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


class GoalUpdatePayload(BaseModel):
    title: str | None = None
    status: GoalStatus | None = None
    summary: str | None = None
    success_metrics: list[str] | None = None
    tags: list[str] | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


class GoalPlanResult(BaseModel):
    goal_id: str
    created_tasks: list[TaskRecord] = Field(default_factory=list)
    summary: str
