from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntentType(str, Enum):
    QUESTION = "question"
    TASK = "task"
    CLARIFICATION = "clarification"
    ROUTINE = "routine"
    CONFLICT = "conflict"


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


class MemoryType(str, Enum):
    PROFILE = "profile"
    TASK = "task"
    KNOWLEDGE = "knowledge"
    REFLECTION = "reflection"


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
    steps: list[ExecutionStep] = Field(default_factory=list)
    confirmation_required: bool = False
    expected_evidence: list[str] = Field(default_factory=list)


class PersonaAnchor(BaseModel):
    identity_statement: str = "A local-first personal intelligence system."
    tone: str = "clear, direct, pragmatic"
    non_negotiables: list[str] = Field(default_factory=list)
    default_planning_style: str = "goal-first"
    autonomy_preference: str = "controlled_autonomy"


class SessionContext(BaseModel):
    active_focus: list[str] = Field(default_factory=list)
    open_loops: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    current_commitments: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class SelfProfile(BaseModel):
    long_term_goals: list[str] = Field(default_factory=list)
    current_phase: str = "bootstrap"
    values: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    risk_style: str = "balanced"
    boundaries: list[str] = Field(default_factory=list)
    relationship_network: list[str] = Field(default_factory=list)
    persona_anchor: PersonaAnchor = Field(default_factory=PersonaAnchor)
    session_context: SessionContext = Field(default_factory=SessionContext)
    updated_at: datetime = Field(default_factory=utc_now)


class StructuredUnderstanding(BaseModel):
    requested_outcome: str
    success_shape: str
    explicit_constraints: list[str] = Field(default_factory=list)
    inferred_constraints: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    time_horizon: str = "unspecified"
    continuation_preference: str = "continue_existing_work_if_possible"


class IntentEnvelope(BaseModel):
    intent_type: IntentType
    goal: str
    urgency: int = Field(ge=1, le=5, default=3)
    risk_level: RiskLevel = RiskLevel.LOW
    needs_confirmation: bool = False
    related_context_ids: list[str] = Field(default_factory=list)
    rationale: str


class CommonsenseAssessment(BaseModel):
    realistic: bool
    safety_ok: bool
    cost_note: str
    notes: list[str] = Field(default_factory=list)


class InsightAssessment(BaseModel):
    is_root_problem: bool
    strategic_position: str
    better_path: str | None = None
    long_term_side_effects: list[str] = Field(default_factory=list)


class CourageAssessment(BaseModel):
    action_mode: str
    should_push_back: bool = False
    needs_confirmation: bool = False
    rationale: str


class CognitionReport(BaseModel):
    commonsense: CommonsenseAssessment
    insight: InsightAssessment
    courage: CourageAssessment
    understanding: StructuredUnderstanding
    suggested_execution_mode: ExecutionMode
    suggested_execution_plan: ExecutionPlan
    suggested_task_tags: list[str] = Field(default_factory=list)
    suggested_success_criteria: list[str] = Field(default_factory=list)
    suggested_next_step: str


class IntakeResponse(BaseModel):
    intent: IntentEnvelope
    cognition: CognitionReport
    task: "TaskRecord | None" = None


class MemoryLayer(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryRecord(BaseModel):
    id: str
    memory_type: MemoryType
    layer: MemoryLayer = MemoryLayer.SEMANTIC
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str = "user"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    freshness: str = "active"
    related_goal_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


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
    execution_plan: ExecutionPlan = Field(default_factory=lambda: ExecutionPlan(mode=ExecutionMode.FILE_ARTIFACT))
    rollback_plan: str | None = None
    blocker_reason: str | None = None
    linked_goal_ids: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CapabilityDescriptor(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    confirmation_required: bool = False
    scopes: list[str] = Field(default_factory=list)
    device_affinity: list[str] = Field(default_factory=list)
    evidence_outputs: list[str] = Field(default_factory=list)


class CapabilityExecutionPayload(BaseModel):
    capability_name: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class CapabilityExecutionResult(BaseModel):
    capability_name: str
    action: str
    status: str
    output: str
    requires_confirmation: bool = False


class InputPayload(BaseModel):
    text: str


class TaskCreatePayload(BaseModel):
    objective: str
    tags: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    linked_goal_ids: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode | None = None
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


class MemoryCreatePayload(BaseModel):
    memory_type: MemoryType
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    layer: MemoryLayer = MemoryLayer.SEMANTIC
    source: str = "user"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    freshness: str = "active"
    related_goal_ids: list[str] = Field(default_factory=list)


class EventRecord(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class ReminderRecord(BaseModel):
    id: str
    title: str
    note: str = ""
    due_hint: str = "unspecified"
    scheduled_for: datetime
    source_task_id: str | None = None
    origin: str | None = None
    last_seen_at: datetime | None = None


class ExecutionRunRecord(BaseModel):
    id: str
    task_id: str
    status: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    created_tasks: list["TaskRecord"] = Field(default_factory=list)
    summary: str


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    UNAVAILABLE = "unavailable"


class DeviceRecord(BaseModel):
    id: str
    name: str
    device_class: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    last_seen_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceUpsertPayload(BaseModel):
    id: str
    name: str
    device_class: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecallItem(BaseModel):
    memory_id: str
    title: str
    layer: MemoryLayer
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class MemoryRecallResponse(BaseModel):
    query: str
    items: list[MemoryRecallItem] = Field(default_factory=list)


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


class EntityRelation(BaseModel):
    id: str
    source_type: str
    source_id: str
    relation_type: str
    target_type: str
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class TimelineItem(BaseModel):
    timestamp: datetime
    phase: str
    title: str
    detail: str
    event_type: str


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
