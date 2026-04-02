from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .self_profile import SelfProfile
from .task import ExecutionMode, ExecutionPlan, RiskLevel, TaskRecord


class IntentType(str, Enum):
    QUESTION = "question"
    TASK = "task"
    CLARIFICATION = "clarification"
    ROUTINE = "routine"
    CONFLICT = "conflict"


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
    task: TaskRecord | None = None


class InputPayload(BaseModel):
    text: str
