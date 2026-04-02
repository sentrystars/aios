from __future__ import annotations

from pydantic import BaseModel, Field

from .candidates import CandidateAcceptanceResult, CandidateSkipDetail
from .task import RiskLevel, TaskStatus


class EscalationPolicy(BaseModel):
    name: str
    create_escalation_task: bool = True
    create_urgent_reminder: bool = False
    promote_risk_level: RiskLevel | None = None
    reminder_due_hint: str = "later today"
    reminder_offset_minutes: int = Field(default=30, ge=1, le=10080)


class EscalationOutcome(BaseModel):
    task_id: str
    status: TaskStatus
    policy_name: str
    actions: list[str] = Field(default_factory=list)
    escalation_task_id: str | None = None
    reminder_id: str | None = None
    risk_promoted: bool = False


class SchedulerTickPayload(BaseModel):
    candidate_limit: int = Field(default=10, ge=1, le=100)
    stale_after_minutes: int = Field(default=60, ge=1, le=10080)
    escalate_after_hits: int = Field(default=2, ge=1, le=20)


class SchedulerTickResult(BaseModel):
    discovered_count: int
    auto_accepted_count: int
    auto_started_count: int
    auto_verified_count: int
    blocked_followup_count: int
    stalled_reminder_count: int
    escalated_count: int
    skipped_count: int
    error_count: int
    accepted: list[CandidateAcceptanceResult] = Field(default_factory=list)
    auto_started_task_ids: list[str] = Field(default_factory=list)
    auto_verified_task_ids: list[str] = Field(default_factory=list)
    blocked_followup_task_ids: list[str] = Field(default_factory=list)
    stalled_task_ids: list[str] = Field(default_factory=list)
    escalated_task_ids: list[str] = Field(default_factory=list)
    escalations: list[EscalationOutcome] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    skip_details: list[CandidateSkipDetail] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
