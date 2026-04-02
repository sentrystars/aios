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
    ImplementationTaskContract,
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

from ai_os.cloud_intelligence import CloudIntentHint, DeepSeekConversationIntelligence
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
    def __init__(
        self,
        memory_engine: MemoryEngine | None = None,
        conversation_intelligence: DeepSeekConversationIntelligence | None = None,
    ) -> None:
        self.memory_engine = memory_engine
        self.conversation_intelligence = conversation_intelligence
        self.last_cloud_hint: CloudIntentHint | None = None

    def analyze(self, intent: IntentEnvelope, profile: SelfProfile) -> CognitionReport:
        lowered = intent.goal.lower()
        cloud_hint = self.conversation_intelligence.analyze(intent.goal, profile) if self.conversation_intelligence else None
        self.last_cloud_hint = cloud_hint
        execution_mode = TaskEngine.infer_execution_mode(intent.goal)
        runtime_name = TaskEngine.infer_runtime_name(intent.goal, execution_mode)
        execution_mode = self._resolve_learned_execution_mode(intent.goal, execution_mode)
        runtime_name = self._resolve_learned_runtime_name(intent.goal, execution_mode, runtime_name)
        if cloud_hint and cloud_hint.execution_mode:
            execution_mode = cloud_hint.execution_mode
        if cloud_hint and cloud_hint.runtime_name and execution_mode == ExecutionMode.FILE_ARTIFACT:
            runtime_name = cloud_hint.runtime_name
        execution_plan = self._build_execution_plan(execution_mode, runtime_name=runtime_name)
        reflection_style = self._reflection_context_style(intent.goal)
        understanding = self._build_understanding(intent.goal, profile, cloud_hint)
        suggested_task_tags: list[str] = list(cloud_hint.suggested_task_tags) if cloud_hint else []
        if cloud_hint:
            suggested_task_tags.extend(["intelligence:cloud", f"intelligence:{cloud_hint.provider}", f"model:{cloud_hint.model}"])
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
    def _build_understanding(
        goal: str,
        profile: SelfProfile,
        cloud_hint: CloudIntentHint | None = None,
    ) -> StructuredUnderstanding:
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
        hint = cloud_hint
        merged_explicit = [*explicit_constraints, *(hint.explicit_constraints if hint else [])]
        merged_inferred = [*inferred_constraints, *(hint.inferred_constraints if hint else [])]
        merged_stakeholders = stakeholders or (hint.stakeholders if hint else [])
        return StructuredUnderstanding(
            requested_outcome=goal,
            success_shape=(
                hint.success_shape
                if hint and hint.success_shape
                else "A tracked next step with evidence, governance fit, and linkage to longer-term context."
            ),
            explicit_constraints=TaskEngine._dedupe_ordered(merged_explicit),
            inferred_constraints=TaskEngine._dedupe_ordered(merged_inferred),
            stakeholders=TaskEngine._dedupe_ordered(merged_stakeholders),
            time_horizon=hint.time_horizon if hint and hint.time_horizon else time_horizon,
            continuation_preference=(
                hint.continuation_preference if hint and hint.continuation_preference else "continue_existing_work_if_possible"
            ),
        )

    def _reflection_context_style(self, goal: str) -> str | None:
        if not self.memory_engine:
            return None
        lowered = goal.lower()
        for memory in self.memory_engine.list():
            if memory.memory_type == MemoryType.LEARNING:
                tags = set(memory.tags)
                for tag in tags:
                    if not tag.startswith("context:"):
                        continue
                    keyword = tag.split(":", 1)[1].strip().lower()
                    if keyword and keyword in lowered:
                        if "learning:guardrail" in tags or "context:cautious" in tags:
                            return "cautious"
                        if "context:bold" in tags:
                            return "bold"
                        if "context:balanced" in tags:
                            return "balanced"
                continue
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

    def _resolve_learned_execution_mode(self, goal: str, default_mode: ExecutionMode) -> ExecutionMode:
        if not self.memory_engine:
            return default_mode
        insights = self.memory_engine.recall_learning(query=goal, limit=5).items
        for insight in insights:
            if insight.category != "execution_mode":
                continue
            for tag in insight.tags:
                if not tag.startswith("context:"):
                    continue
                raw_mode = tag.split(":", 1)[1]
                try:
                    return ExecutionMode(raw_mode)
                except ValueError:
                    continue
        return default_mode

    def _resolve_learned_runtime_name(
        self, goal: str, mode: ExecutionMode, default_runtime_name: str | None
    ) -> str | None:
        if not self.memory_engine or mode != ExecutionMode.FILE_ARTIFACT:
            return default_runtime_name
        insights = self.memory_engine.recall_learning(query=goal, limit=5).items
        for insight in insights:
            if insight.category != "runtime":
                continue
            for tag in insight.tags:
                if tag.startswith("context:"):
                    candidate = tag.split(":", 1)[1]
                    if candidate != "none":
                        return candidate
        return default_runtime_name

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
    def __init__(
        self,
        governance: GovernanceLayer,
        conversation_intelligence: DeepSeekConversationIntelligence | None = None,
    ) -> None:
        self.governance = governance
        self.conversation_intelligence = conversation_intelligence
        self.last_cloud_hint: CloudIntentHint | None = None

    def evaluate(self, payload: InputPayload, profile: SelfProfile) -> IntentEnvelope:
        text = payload.text.strip()
        lowered = text.lower()
        risk_level, needs_confirmation, governance_note = self.governance.assess(text)
        cloud_hint = self.conversation_intelligence.analyze(text, profile) if self.conversation_intelligence else None
        self.last_cloud_hint = cloud_hint

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
        elif cloud_hint and cloud_hint.intent_type:
            intent_type = cloud_hint.intent_type
            if cloud_hint.needs_confirmation is not None:
                needs_confirmation = needs_confirmation or cloud_hint.needs_confirmation
            if cloud_hint.rationale:
                rationale = f"{rationale} Cloud understanding: {cloud_hint.rationale}"

        return IntentEnvelope(
            intent_type=intent_type,
            goal=text,
            urgency=(
                cloud_hint.urgency
                if cloud_hint and cloud_hint.urgency is not None
                else 4
                if any(token in lowered for token in ("urgent", "asap", "today", "紧急", "尽快", "今天"))
                else 3
            ),
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

    def __init__(self, repo: TaskRepository, events: EventRepository, memory_engine: MemoryEngine | None = None) -> None:
        self.repo = repo
        self.events = events
        self.memory_engine = memory_engine

    def create(self, payload: TaskCreatePayload) -> TaskRecord:
        task_data = payload.model_dump()
        mode = payload.execution_mode or self._resolve_execution_mode(payload.objective)
        runtime_name = payload.runtime_name or self._resolve_runtime_name(payload.objective, mode)
        task_data["execution_mode"] = mode
        task_data["runtime_name"] = runtime_name
        task_data["execution_plan"] = payload.execution_plan or self.build_execution_plan(mode, runtime_name=runtime_name)
        task = TaskRecord(id=str(uuid4()), **task_data)
        if not task.implementation_contract:
            task.implementation_contract = self._build_implementation_contract(task)
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
        task.execution_mode = self._resolve_execution_mode(task.objective)
        task.runtime_name = self._resolve_runtime_name(task.objective, task.execution_mode)
        task.execution_plan = self.build_execution_plan(task.execution_mode, runtime_name=task.runtime_name)
        task.success_criteria = self._augment_success_criteria(task)
        task.implementation_contract = self._build_implementation_contract(task)
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
    def _dedupe_ordered(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _generate_subtasks(self, task: TaskRecord) -> list[str]:
        base_steps = []
        if task.objective.startswith("Replan task:"):
            source_task = self._source_task(task)
            target_objective = source_task.objective if source_task else task.objective.removeprefix("Replan task:").strip()
            base_steps.extend(
                [
                    f"Review the failed evidence and blocker history for: {target_objective}",
                    f"Revise the execution path and checks for: {target_objective}",
                    f"Validate that the revised plan closes the prior verification gap for: {target_objective}",
                ]
            )
        else:
            base_steps.extend(
                [
                    f"Clarify the outcome and constraints for: {task.objective}",
                    f"Execute the primary work required for: {task.objective}",
                    f"Verify the result against the success criteria for: {task.objective}",
                ]
            )
        if task.success_criteria:
            base_steps.insert(1, "Translate the success criteria into concrete checks.")
        learning_steps = self._learning_subtasks(task)
        source_steps = self._source_task_subtasks(task)
        return self._dedupe_ordered([*base_steps, *source_steps, *learning_steps])

    def _augment_success_criteria(self, task: TaskRecord) -> list[str]:
        criteria = list(task.success_criteria)
        if self._learning_subtasks(task) and "Relevant learned guidance is incorporated into the plan." not in criteria:
            criteria.append("Relevant learned guidance is incorporated into the plan.")
        if task.objective.startswith("Replan task:"):
            replan_criterion = "The revised plan addresses the previously failed verification evidence."
            if replan_criterion not in criteria:
                criteria.append(replan_criterion)
        return criteria

    def _learning_subtasks(self, task: TaskRecord) -> list[str]:
        if not self.memory_engine:
            return []
        runtime_name = task.runtime_name or task.execution_plan.runtime_name or ""
        query = " ".join(part for part in [task.objective, runtime_name] if part).strip()
        insights = self.memory_engine.recall_learning(query=query, limit=3).items
        steps: list[str] = []
        for insight in insights:
            label = insight.title.lower()
            if insight.category == "guardrail":
                steps.append(f"Preserve learned guardrail during planning: {label}")
            elif insight.category == "runtime":
                steps.append(f"Apply learned runtime guidance before execution: {label}")
            else:
                steps.append(f"Incorporate learned {insight.category} guidance into the plan: {label}")
        return steps

    def _resolve_execution_mode(self, objective: str) -> ExecutionMode:
        default_mode = self.infer_execution_mode(objective)
        if not self.memory_engine:
            return default_mode
        insights = self.memory_engine.recall_learning(query=objective, limit=5).items
        for insight in insights:
            if insight.category != "execution_mode":
                continue
            for tag in insight.tags:
                if not tag.startswith("context:"):
                    continue
                raw_mode = tag.split(":", 1)[1]
                try:
                    return ExecutionMode(raw_mode)
                except ValueError:
                    continue
        return default_mode

    def _resolve_runtime_name(self, objective: str, mode: ExecutionMode) -> str | None:
        default_runtime_name = self.infer_runtime_name(objective, mode)
        if not self.memory_engine or mode != ExecutionMode.FILE_ARTIFACT:
            return default_runtime_name
        insights = self.memory_engine.recall_learning(query=objective, limit=5).items
        for insight in insights:
            if insight.category != "runtime":
                continue
            for tag in insight.tags:
                if not tag.startswith("context:"):
                    continue
                candidate = tag.split(":", 1)[1]
                if candidate != "none":
                    return candidate
        return default_runtime_name

    def _source_task(self, task: TaskRecord) -> TaskRecord | None:
        for tag in task.tags:
            if not tag.startswith("source_task:"):
                continue
            return self.repo.get(tag.split(":", 1)[1])
        return None

    def _source_task_subtasks(self, task: TaskRecord) -> list[str]:
        source_task = self._source_task(task)
        if not source_task:
            return []
        steps: list[str] = []
        if source_task.blocker_reason:
            steps.append(f"Account for blocker reason: {source_task.blocker_reason}")
        if source_task.verification_notes:
            steps.append(f"Review prior verification notes from source task {source_task.id}")
        return steps

    def _build_implementation_contract(self, task: TaskRecord) -> ImplementationTaskContract | None:
        if task.execution_mode == ExecutionMode.MESSAGE_DRAFT:
            return ImplementationTaskContract(
                summary=task.objective,
                deliverable_type="message_draft",
                execution_scope="communication",
                acceptance_criteria=task.success_criteria,
                constraints=["Do not send without explicit confirmation."],
                planned_subtasks=task.subtasks,
                expected_outputs=["Drafted outbound message"],
                output_requirements=[
                    ImplementationTaskContract.OutputRequirement(
                        key="message_draft",
                        label="Drafted outbound message",
                        source="message_verification",
                    )
                ],
                repo_instructions=[],
                preferred_runtime=task.runtime_name or task.execution_plan.runtime_name,
            )
        if task.execution_mode == ExecutionMode.CALENDAR_EVENT:
            return ImplementationTaskContract(
                summary=task.objective,
                deliverable_type="calendar_event",
                execution_scope="local_calendar",
                acceptance_criteria=task.success_criteria,
                constraints=task.verification_notes,
                planned_subtasks=task.subtasks,
                expected_outputs=["Calendar event scheduled"],
                output_requirements=[
                    ImplementationTaskContract.OutputRequirement(
                        key="calendar_event",
                        label="Calendar event scheduled",
                        source="calendar_verification",
                    )
                ],
                repo_instructions=[],
                preferred_runtime=task.runtime_name or task.execution_plan.runtime_name,
            )
        if task.execution_mode == ExecutionMode.REMINDER:
            return ImplementationTaskContract(
                summary=task.objective,
                deliverable_type="reminder",
                execution_scope="local_reminders",
                acceptance_criteria=task.success_criteria,
                constraints=[],
                planned_subtasks=task.subtasks,
                expected_outputs=["Reminder created"],
                output_requirements=[
                    ImplementationTaskContract.OutputRequirement(
                        key="reminder",
                        label="Reminder created",
                        source="reminder_verification",
                    )
                ],
                repo_instructions=[],
                preferred_runtime=task.runtime_name or task.execution_plan.runtime_name,
            )
        if task.execution_mode == ExecutionMode.MEMORY_CAPTURE:
            return ImplementationTaskContract(
                summary=task.objective,
                deliverable_type="memory_record",
                execution_scope="memory",
                acceptance_criteria=task.success_criteria,
                constraints=[],
                planned_subtasks=task.subtasks,
                expected_outputs=["Structured memory record created"],
                output_requirements=[
                    ImplementationTaskContract.OutputRequirement(
                        key="memory_record",
                        label="Structured memory record created",
                        source="memory_verification",
                    )
                ],
                repo_instructions=[],
                preferred_runtime=task.runtime_name or task.execution_plan.runtime_name,
            )
        deliverable_type = "code_change" if self._looks_like_code_work(task.objective) else "document_artifact"
        constraints = list(task.intelligence_trace.get("explicit_constraints", [])) if task.intelligence_trace else []
        if task.execution_plan.confirmation_required:
            constraints.append("Require confirmation before external side effects.")
        repo_instructions = [
            "Read the repository before editing.",
            "Prefer minimal, reviewable changes tied to the acceptance criteria.",
            "Return verification evidence with the implementation result.",
        ]
        if task.objective.startswith("Replan task:"):
            repo_instructions.append("Use prior blocker and verification history to revise the implementation path.")
        expected_outputs = ["Updated artifact or code changes", "Verification evidence"]
        output_requirements = [
            ImplementationTaskContract.OutputRequirement(
                key="artifact_or_code_change",
                label="Updated artifact or code changes",
                source="artifact_or_diff",
            ),
            ImplementationTaskContract.OutputRequirement(
                key="verification_evidence",
                label="Verification evidence",
                source="verification_evidence",
                required=False,
            ),
        ]
        if deliverable_type == "code_change":
            expected_outputs = ["Modified files", "Commands or tests run", "Verification evidence"]
            output_requirements = [
                ImplementationTaskContract.OutputRequirement(
                    key="changed_files",
                    label="Modified files",
                    source="runtime_changed_files",
                ),
                ImplementationTaskContract.OutputRequirement(
                    key="commands_or_tests",
                    label="Commands or tests run",
                    source="runtime_commands_or_tests",
                ),
                ImplementationTaskContract.OutputRequirement(
                    key="verification_evidence",
                    label="Verification evidence",
                    source="verification_evidence",
                ),
            ]
        return ImplementationTaskContract(
            summary=task.objective,
            deliverable_type=deliverable_type,
            execution_scope="repository" if deliverable_type == "code_change" else "workspace_artifact",
            acceptance_criteria=task.success_criteria,
            constraints=self._dedupe_ordered(constraints),
            planned_subtasks=task.subtasks,
            expected_outputs=expected_outputs,
            output_requirements=output_requirements,
            repo_instructions=repo_instructions,
            preferred_runtime=task.runtime_name or task.execution_plan.runtime_name,
        )

    @staticmethod
    def _looks_like_code_work(objective: str) -> bool:
        lowered = objective.lower()
        return any(token in lowered for token in ("code", "repo", "git", "refactor", "implement", "feature", "bug", "runtime", "api"))

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
        lowered_notes = [note.lower().strip() for note in task.verification_notes]
        if any(
            note.startswith("missing ")
            or note.startswith("pending evidence ")
            or note == "runtime execution failed"
            or note.startswith("runtime blocker:")
            for note in lowered_notes
        ):
            return False
        if not task.success_criteria:
            return True
        return True

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
