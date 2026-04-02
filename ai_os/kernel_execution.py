from __future__ import annotations


from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ai_os.domain import (
    CalendarEventRecord,
    CandidateAcceptancePayload,
    CandidateAcceptanceResult,
    CandidateAutoAcceptPayload,
    CandidateBatchAutoAcceptPayload,
    CandidateBatchAutoAcceptResult,
    CandidateDeferPayload,
    CandidateDeferResult,
    CandidateSkipDetail,
    CandidateTask,
    CapabilityExecutionPayload,
    CapabilityExecutionResult,
    CapabilityDescriptor,
    CognitionReport,
    CommonsenseAssessment,
    CourageAssessment,
    DeviceRecord,
    DeviceStatus,
    DeviceUpsertPayload,
    EscalationOutcome,
    EscalationPolicy,
    ExecutionPlan,
    ExecutionMode,
    ExecutionStep,
    EntityRelation,
    EventRecord,
    ExecutionRunRecord,
    GoalCreatePayload,
    GoalPlanResult,
    GoalRecord,
    GoalStatus,
    GoalUpdatePayload,
    InputPayload,
    IntakeResponse,
    InsightAssessment,
    IntentEnvelope,
    IntentType,
    MemoryCreatePayload,
    MemoryLayer,
    MemoryRecallItem,
    MemoryRecallResponse,
    MemoryRecord,
    MemoryType,
    ReminderRecord,
    RiskLevel,
    SchedulerTickPayload,
    SchedulerTickResult,
    SelfProfile,
    StructuredUnderstanding,
    TaskAdvancePayload,
    TaskConfirmationPayload,
    TaskCreatePayload,
    TaskReflectionPayload,
    TaskRecord,
    TaskStatus,
    TaskVerificationPayload,
    TimelineItem,
    utc_now,
)
from ai_os.storage import (
    Database,
    DeviceRepository,
    EventRepository,
    ExecutionRunRepository,
    GoalRepository,
    MemoryRepository,
    RelationRepository,
    SelfRepository,
    TaskRepository,
)

from ai_os.kernel_services import MemoryEngine

class GovernanceLayer:
    def assess(self, text: str) -> tuple[RiskLevel, bool, str]:
        lowered = text.lower()
        risky_tokens = {"delete", "remove", "shutdown", "kill", "transfer", "wire", "删除", "移除", "转账", "汇款"}
        medium_tokens = {"send", "book", "schedule", "buy", "发送", "预订", "安排", "日历", "会议", "提醒"}
        if any(token in lowered for token in risky_tokens):
            return RiskLevel.HIGH, True, "Potentially destructive or irreversible action."
        if any(token in lowered for token in medium_tokens):
            return RiskLevel.MEDIUM, False, "Action affects external systems or commitments."
        return RiskLevel.LOW, False, "Low-risk request."


class CognitionEngine:
    def __init__(self, memory_engine: MemoryEngine | None = None) -> None:
        self.memory_engine = memory_engine

    def analyze(self, intent: IntentEnvelope, profile: SelfProfile) -> CognitionReport:
        lowered = intent.goal.lower()
        execution_mode = TaskEngine.infer_execution_mode(intent.goal)
        runtime_name = TaskEngine.infer_runtime_name(intent.goal, execution_mode)
        execution_plan = self._build_execution_plan(execution_mode, runtime_name=runtime_name)
        reflection_style = self._reflection_context_style(intent.goal)
        understanding = self._build_understanding(intent.goal, profile)
        suggested_task_tags: list[str] = []
        realistic = not any(token in lowered for token in ("teleport", "infinite", "instantly rich"))
        safety_ok = intent.risk_level != RiskLevel.HIGH
        notes: list[str] = []
        if not realistic:
            notes.append("Request conflicts with basic real-world constraints.")
        if intent.risk_level == RiskLevel.HIGH:
            notes.append("High-risk execution should be gated behind explicit approval.")
        if reflection_style == "cautious":
            notes.append("Reflection guardrail suggests cautious handling for this request.")

        better_path = None
        is_root_problem = True
        if any(token in lowered for token in ("urgent", "asap")):
            better_path = "Clarify the actual deadline and impact before over-prioritizing."
            is_root_problem = False

        strategic_position = (
            f"Aligned with current phase '{profile.current_phase}'."
            if profile.current_phase
            else "No current phase set."
        )

        if intent.intent_type == IntentType.QUESTION:
            action_mode = "answer"
            should_push_back = False
            needs_confirmation = False
            rationale = "Direct response is lower cost than spawning tracked work."
            next_step = "Answer the question and only open a task if follow-through is requested."
            success_criteria: list[str] = []
        elif intent.intent_type == IntentType.CONFLICT:
            action_mode = "push_back"
            should_push_back = True
            needs_confirmation = True
            rationale = "Request appears to cross an explicit boundary and should be challenged."
            next_step = "Surface the conflict, explain the boundary, and ask for explicit override."
            success_criteria = []
        else:
            action_mode = "execute" if not intent.needs_confirmation else "confirm_then_execute"
            should_push_back = False
            needs_confirmation = intent.needs_confirmation
            rationale = "The request should become tracked work with a clear next step."
            next_step = "Create or update a task, then move it toward planning."
            success_criteria = [
                "The request is represented as a tracked task.",
                "A next action is identified.",
                "Risk handling matches governance policy.",
            ]
            if understanding.stakeholders:
                success_criteria.append("Relevant stakeholders are acknowledged in the execution path.")
            if understanding.explicit_constraints or understanding.inferred_constraints:
                success_criteria.append("Important constraints are preserved during execution.")
            if reflection_style == "cautious":
                action_mode = "confirm_then_execute"
                needs_confirmation = True
                rationale = "Past reflection guardrails indicate this type of task should be handled cautiously."
                next_step = "Create the task, surface the guardrail, and require confirmation before execution."
                execution_plan = execution_plan.model_copy(update={"confirmation_required": True})
                success_criteria.append("Relevant historical guardrails are surfaced before execution.")
                success_criteria.append("Explicit confirmation or risk review happens before external action.")
                suggested_task_tags.extend(["governance:cautious", "guardrail:reflection"])

        return CognitionReport(
            commonsense=CommonsenseAssessment(
                realistic=realistic,
                safety_ok=safety_ok,
                cost_note="Low operational cost for digital-only steps." if intent.risk_level == RiskLevel.LOW else "Execution may incur external or irreversible cost.",
                notes=notes,
            ),
            insight=InsightAssessment(
                is_root_problem=is_root_problem,
                strategic_position=strategic_position,
                better_path=better_path,
                long_term_side_effects=["May create coordination debt if executed without review."]
                if intent.risk_level != RiskLevel.LOW
                else [],
            ),
            courage=CourageAssessment(
                action_mode=action_mode,
                should_push_back=should_push_back,
                needs_confirmation=needs_confirmation,
                rationale=rationale,
            ),
            understanding=understanding,
            suggested_execution_mode=execution_mode,
            suggested_execution_plan=execution_plan,
            suggested_task_tags=suggested_task_tags,
            suggested_success_criteria=success_criteria,
            suggested_next_step=next_step,
        )

    @staticmethod
    def _build_understanding(goal: str, profile: SelfProfile) -> StructuredUnderstanding:
        lowered = goal.lower()
        explicit_constraints: list[str] = []
        inferred_constraints: list[str] = []
        stakeholders: list[str] = []
        if "today" in lowered or "今天" in lowered:
            explicit_constraints.append("Time-bound: today")
        if "tomorrow" in lowered or "明天" in lowered:
            explicit_constraints.append("Time-bound: tomorrow")
        if "quick" in lowered or "brief" in lowered or "尽快" in lowered or "简短" in lowered:
            explicit_constraints.append("Keep output lightweight")
        if "email" in lowered or "message" in lowered or "notify" in lowered or "邮件" in lowered or "消息" in lowered or "通知" in lowered:
            inferred_constraints.append("External communication requires review before send")
        if "plan" in lowered or "计划" in lowered:
            inferred_constraints.append("Produce structured next actions rather than a single answer")
        known_contacts = [
            item.split(":", 1)[1].strip()
            for item in profile.relationship_network
            if ":" in item and item.split(":", 1)[1].strip()
        ]
        stakeholders = [name for name in known_contacts if name.lower() in lowered]
        if not stakeholders and profile.current_phase:
            stakeholders = [f"self:{profile.current_phase}"]
        time_horizon = (
            "today"
            if any(token in lowered for token in ("today", "今天", "今晚", "下午", "上午"))
            else "near_term"
            if any(token in lowered for token in ("week", "tomorrow", "soon", "本周", "明天", "稍后"))
            else "unspecified"
        )
        return StructuredUnderstanding(
            requested_outcome=goal,
            success_shape="A tracked next step with evidence, governance fit, and linkage to longer-term context.",
            explicit_constraints=explicit_constraints,
            inferred_constraints=inferred_constraints,
            stakeholders=stakeholders,
            time_horizon=time_horizon,
            continuation_preference="continue_existing_work_if_possible",
        )

    def _reflection_context_style(self, goal: str) -> str | None:
        if not self.memory_engine:
            return None
        lowered = goal.lower()
        for memory in self.memory_engine.list():
            if memory.memory_type != MemoryType.REFLECTION:
                continue
            for line in memory.content.splitlines():
                normalized = line.strip().lstrip("- ").strip()
                if not normalized.startswith("guardrail:"):
                    continue
                parts = normalized.split(":", 2)
                if len(parts) != 3:
                    continue
                _, raw_style, raw_keyword = parts
                style = raw_style.strip().lower()
                keyword = raw_keyword.strip().lower()
                if keyword and keyword in lowered:
                    if style in {"high_risk", "protected", "cautious"}:
                        return "cautious"
                    if style in {"balanced", "bold"}:
                        return style
        return None

    @staticmethod
    def _build_execution_plan(mode: ExecutionMode, runtime_name: str | None = None) -> ExecutionPlan:
        if mode == ExecutionMode.MEMORY_CAPTURE:
            return ExecutionPlan(
                mode=mode,
                runtime_name=runtime_name,
                steps=[
                    ExecutionStep(
                        capability_name="memory_engine",
                        action="create_knowledge_record",
                        purpose="Capture the request as structured memory.",
                    )
                ],
                confirmation_required=False,
                expected_evidence=["Memory record created"],
            )
        if mode == ExecutionMode.MESSAGE_DRAFT:
            return ExecutionPlan(
                mode=mode,
                runtime_name=runtime_name,
                steps=[
                    ExecutionStep(
                        capability_name="messaging",
                        action="prepare",
                        purpose="Prepare the outbound message without sending it.",
                    )
                ],
                confirmation_required=True,
                expected_evidence=["Drafted outbound message", "User confirmation pending or complete"],
            )
        if mode == ExecutionMode.REMINDER:
            return ExecutionPlan(
                mode=mode,
                runtime_name=runtime_name,
                steps=[
                    ExecutionStep(
                        capability_name="reminders",
                        action="create",
                        purpose="Create a local reminder entry for future follow-up.",
                    )
                ],
                confirmation_required=False,
                expected_evidence=["Reminder scheduled"],
            )
        if mode == ExecutionMode.CALENDAR_EVENT:
            return ExecutionPlan(
                mode=mode,
                runtime_name=runtime_name,
                steps=[
                    ExecutionStep(
                        capability_name="calendar",
                        action="create",
                        purpose="Place the work onto the local calendar as a concrete time block.",
                    )
                ],
                confirmation_required=False,
                expected_evidence=["Calendar event scheduled"],
            )
        return ExecutionPlan(
            mode=mode,
            runtime_name=runtime_name,
            steps=[
                ExecutionStep(
                    capability_name="local_files",
                    action="write_text",
                    purpose="Write a task artifact into the workspace.",
                )
            ],
            confirmation_required=False,
            expected_evidence=["Task artifact file exists"],
        )


class IntentEngine:
    def __init__(self, governance: GovernanceLayer) -> None:
        self.governance = governance

    def evaluate(self, payload: InputPayload, profile: SelfProfile) -> IntentEnvelope:
        text = payload.text.strip()
        lowered = text.lower()
        risk_level, needs_confirmation, governance_note = self.governance.assess(text)

        if not text:
            intent_type = IntentType.CLARIFICATION
            rationale = "Empty input requires clarification."
        elif lowered.startswith(("why", "what", "how", "when", "where")) or text.endswith("?"):
            intent_type = IntentType.QUESTION
            rationale = "Input is phrased as a question."
        elif any(token in lowered for token in ("clarify", "explain", "what do you mean")):
            intent_type = IntentType.CLARIFICATION
            rationale = "Input explicitly asks for clarification."
        elif any(token in lowered for token in ("every day", "daily", "weekly", "remind")):
            intent_type = IntentType.ROUTINE
            rationale = "Input looks like a repeatable or scheduled workflow."
        else:
            intent_type = IntentType.TASK
            rationale = "Input is action-oriented and should be tracked as work."

        if profile.boundaries and any(boundary.lower() in lowered for boundary in profile.boundaries):
            intent_type = IntentType.CONFLICT
            needs_confirmation = True
            rationale = "Input appears to cross a declared user boundary."

        return IntentEnvelope(
            intent_type=intent_type,
            goal=text,
            urgency=4 if any(token in lowered for token in ("urgent", "asap", "today", "紧急", "尽快", "今天")) else 3,
            risk_level=risk_level,
            needs_confirmation=needs_confirmation,
            related_context_ids=[],
            rationale=f"{rationale} {governance_note}",
        )


class TaskEngine:
    VALID_TRANSITIONS = {
        TaskStatus.CAPTURED: {TaskStatus.CLARIFYING, TaskStatus.PLANNED, TaskStatus.ARCHIVED},
        TaskStatus.CLARIFYING: {TaskStatus.PLANNED, TaskStatus.ARCHIVED},
        TaskStatus.PLANNED: {TaskStatus.EXECUTING, TaskStatus.BLOCKED, TaskStatus.ARCHIVED},
        TaskStatus.EXECUTING: {TaskStatus.BLOCKED, TaskStatus.VERIFYING, TaskStatus.ARCHIVED},
        TaskStatus.BLOCKED: {TaskStatus.PLANNED, TaskStatus.EXECUTING, TaskStatus.ARCHIVED},
        TaskStatus.VERIFYING: {TaskStatus.DONE, TaskStatus.EXECUTING, TaskStatus.ARCHIVED},
        TaskStatus.DONE: {TaskStatus.ARCHIVED},
        TaskStatus.ARCHIVED: set(),
    }

    def __init__(self, repo: TaskRepository, events: EventRepository) -> None:
        self.repo = repo
        self.events = events

    def create(self, payload: TaskCreatePayload) -> TaskRecord:
        task_data = payload.model_dump()
        mode = payload.execution_mode or self.infer_execution_mode(payload.objective)
        runtime_name = payload.runtime_name or self.infer_runtime_name(payload.objective, mode)
        task_data["execution_mode"] = mode
        task_data["runtime_name"] = runtime_name
        task_data["execution_plan"] = payload.execution_plan or self.build_execution_plan(mode, runtime_name=runtime_name)
        task = TaskRecord(id=str(uuid4()), **task_data)
        self.events.append("task.created", task.model_dump(mode="json"))
        return self.repo.create(task)

    def list(self) -> list[TaskRecord]:
        return self.repo.list()

    def advance(self, task_id: str, payload: TaskAdvancePayload) -> TaskRecord:
        task = self.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if payload.status not in self.VALID_TRANSITIONS[task.status]:
            raise ValueError(f"Invalid transition from {task.status.value} to {payload.status.value}.")
        task.status = payload.status
        task.blocker_reason = payload.blocker_reason
        task.updated_at = utc_now()
        self.events.append(
            "task.advanced",
            {"task_id": task_id, "status": task.status.value, "blocker_reason": payload.blocker_reason},
        )
        return self.repo.update(task)

    def ensure_from_intent(self, intent: IntentEnvelope, cognition: CognitionReport) -> TaskRecord | None:
        if intent.intent_type not in {IntentType.TASK, IntentType.ROUTINE}:
            return None
        return self.create(
            TaskCreatePayload(
                objective=intent.goal,
                tags=cognition.suggested_task_tags,
                success_criteria=cognition.suggested_success_criteria,
                risk_level=intent.risk_level,
                execution_mode=cognition.suggested_execution_mode,
                runtime_name=cognition.suggested_execution_plan.runtime_name,
                execution_plan=cognition.suggested_execution_plan,
                rollback_plan="Revert the last external action and notify the user if outcome is unacceptable."
                if intent.risk_level != RiskLevel.LOW
                else None,
            )
        )

    def plan(self, task_id: str) -> TaskRecord:
        task = self.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if task.status in {TaskStatus.DONE, TaskStatus.ARCHIVED}:
            raise ValueError(f"Cannot plan task from terminal state {task.status.value}.")

        task.subtasks = self._generate_subtasks(task)
        task.execution_mode = self.infer_execution_mode(task.objective)
        task.runtime_name = self.infer_runtime_name(task.objective, task.execution_mode)
        task.execution_plan = self.build_execution_plan(task.execution_mode, runtime_name=task.runtime_name)
        task.status = TaskStatus.PLANNED
        task.blocker_reason = None
        task.updated_at = utc_now()
        self.events.append(
            "task.planned",
            {
                "task_id": task.id,
                "subtasks": task.subtasks,
                "status": task.status.value,
                "execution_mode": task.execution_mode.value,
                "runtime_name": task.runtime_name,
                "execution_plan": task.execution_plan.model_dump(mode="json"),
            },
        )
        return self.repo.update(task)

    def mark_executing(self, task_id: str) -> TaskRecord:
        task = self.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if task.status not in {TaskStatus.PLANNED, TaskStatus.BLOCKED}:
            raise ValueError(f"Cannot start execution from {task.status.value}.")
        task.status = TaskStatus.EXECUTING
        task.blocker_reason = None
        task.updated_at = utc_now()
        self.events.append("task.executing", {"task_id": task.id, "status": task.status.value})
        return self.repo.update(task)

    def verify(self, task_id: str, payload: TaskVerificationPayload) -> TaskRecord:
        task = self.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if task.status not in {TaskStatus.EXECUTING, TaskStatus.VERIFYING}:
            raise ValueError(f"Cannot verify task from {task.status.value}.")
        task.verification_notes = self._run_checks(task, payload)
        task.status = TaskStatus.DONE if self._passes_verification(task) else TaskStatus.BLOCKED
        task.blocker_reason = None if task.status == TaskStatus.DONE else "Verification did not satisfy all success criteria."
        task.updated_at = utc_now()
        self.events.append(
            "task.verified",
            {"task_id": task.id, "status": task.status.value, "verification_notes": task.verification_notes},
        )
        return self.repo.update(task)

    @staticmethod
    def _generate_subtasks(task: TaskRecord) -> list[str]:
        base_steps = [
            f"Clarify the outcome and constraints for: {task.objective}",
            f"Execute the primary work required for: {task.objective}",
            f"Verify the result against the success criteria for: {task.objective}",
        ]
        if task.success_criteria:
            base_steps.insert(1, "Translate the success criteria into concrete checks.")
        return base_steps

    @staticmethod
    def _run_checks(task: TaskRecord, payload: TaskVerificationPayload) -> list[str]:
        notes = list(payload.checks)
        if payload.verifier_notes:
            notes.append(payload.verifier_notes)
        if not notes and task.success_criteria:
            notes = [f"Pending evidence for criterion: {criterion}" for criterion in task.success_criteria]
        return notes

    @staticmethod
    def _passes_verification(task: TaskRecord) -> bool:
        if not task.success_criteria:
            return True
        combined_notes = " ".join(task.verification_notes).lower()
        return not any(token in combined_notes for token in ("missing", "failed", "pending"))

    @staticmethod
    def infer_execution_mode(objective: str) -> ExecutionMode:
        lowered = objective.lower()
        if any(token in lowered for token in ("remember", "capture", "log", "record note", "记住", "记录", "备忘")):
            return ExecutionMode.MEMORY_CAPTURE
        if any(token in lowered for token in ("calendar", "schedule time", "time block", "working session", "meeting", "focus block", "日历", "日程", "会议", "评审", "安排")):
            return ExecutionMode.CALENDAR_EVENT
        if any(token in lowered for token in ("remind", "schedule", "follow up tomorrow", "later today", "提醒", "稍后提醒", "回头提醒")):
            return ExecutionMode.REMINDER
        if any(token in lowered for token in ("message", "notify", "email", "text ", "发消息", "通知", "邮件", "联系")):
            return ExecutionMode.MESSAGE_DRAFT
        return ExecutionMode.FILE_ARTIFACT

    @staticmethod
    def infer_runtime_name(objective: str, mode: ExecutionMode) -> str | None:
        lowered = objective.lower()
        if mode == ExecutionMode.FILE_ARTIFACT and any(
            token in lowered for token in ("code", "repo", "git", "refactor", "implement", "feature", "bug", "api", "runtime")
        ):
            return "claude-code"
        return None

    @staticmethod
    def build_execution_plan(mode: ExecutionMode, runtime_name: str | None = None) -> ExecutionPlan:
        return CognitionEngine._build_execution_plan(mode, runtime_name=runtime_name)
