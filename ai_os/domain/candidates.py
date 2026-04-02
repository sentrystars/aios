from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .task import TaskRecord


class CandidateTask(BaseModel):
    kind: str
    title: str
    detail: str
    source_task_id: str | None = None
    reason_code: str
    trigger_source: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(ge=1, le=5, default=3)
    auto_acceptable: bool = False
    needs_confirmation: bool = False


class CandidateAcceptancePayload(BaseModel):
    kind: str
    title: str
    detail: str
    source_task_id: str | None = None
    reason_code: str | None = None
    trigger_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateAcceptanceResult(BaseModel):
    action: str
    task: TaskRecord


class CandidateAutoAcceptPayload(BaseModel):
    kind: str
    title: str
    detail: str
    source_task_id: str | None = None
    reason_code: str
    trigger_source: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_acceptable: bool
    needs_confirmation: bool = False


class CandidateBatchAutoAcceptPayload(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class CandidateSkipDetail(BaseModel):
    kind: str
    title: str
    reason: str
    source_task_id: str | None = None
    reason_code: str | None = None
    trigger_source: str | None = None


class CandidateBatchAutoAcceptResult(BaseModel):
    accepted: list[CandidateAcceptanceResult] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    skip_details: list[CandidateSkipDetail] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CandidateDeferPayload(BaseModel):
    kind: str
    title: str
    detail: str
    reason_code: str | None = None
    trigger_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    due_hint: str | None = None
    scheduled_for: datetime | None = None


class CandidateDeferResult(BaseModel):
    action: str
    metadata: dict[str, Any] = Field(default_factory=dict)
