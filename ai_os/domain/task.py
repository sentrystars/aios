from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .common import utc_now


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    CAPTURED = "captured"
    CLARIFYING = "clarifying"
    PLANNED = "planned"
    EXECUTING = "executing"
    BLOCKED = "blocked"
    VERIFYING = "verifying"
    DONE = "done"
    ARCHIVED = "archived"


class ExecutionMode(str, Enum):
    FILE_ARTIFACT = "file_artifact"
    MEMORY_CAPTURE = "memory_capture"
    MESSAGE_DRAFT = "message_draft"
    REMINDER = "reminder"
    CALENDAR_EVENT = "calendar_event"


class ExecutionStep(BaseModel):
    capability_name: str
    action: str
    purpose: str


class ExecutionPlan(BaseModel):
    mode: ExecutionMode
    runtime_name: str | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    confirmation_required: bool = False
    expected_evidence: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    id: str
    objective: str
    tags: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    owner: str = "ai_os"
    status: TaskStatus = TaskStatus.CAPTURED
    subtasks: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    execution_mode: ExecutionMode = ExecutionMode.FILE_ARTIFACT
    runtime_name: str | None = None
    execution_plan: ExecutionPlan = Field(default_factory=lambda: ExecutionPlan(mode=ExecutionMode.FILE_ARTIFACT))
    rollback_plan: str | None = None
    blocker_reason: str | None = None
    linked_goal_ids: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskCreatePayload(BaseModel):
    objective: str
    tags: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    linked_goal_ids: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode | None = None
    runtime_name: str | None = None
    execution_plan: ExecutionPlan | None = None
    rollback_plan: str | None = None


class TaskAdvancePayload(BaseModel):
    status: TaskStatus
    blocker_reason: str | None = None


class TaskVerificationPayload(BaseModel):
    checks: list[str] = Field(default_factory=list)
    verifier_notes: str | None = None


class TaskConfirmationPayload(BaseModel):
    approved: bool
    note: str | None = None


class TaskReflectionPayload(BaseModel):
    summary: str
    lessons: list[str] = Field(default_factory=list)


class ExecutionRunRecord(BaseModel):
    id: str
    task_id: str
    status: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
