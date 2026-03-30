from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ai_os.domain import (
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
    EscalationOutcome,
    EscalationPolicy,
    ExecutionPlan,
    ExecutionMode,
    ExecutionStep,
    EntityRelation,
    EventRecord,
    ExecutionRunRecord,
    InputPayload,
    IntakeResponse,
    InsightAssessment,
    IntentEnvelope,
    IntentType,
    MemoryCreatePayload,
    MemoryRecord,
    MemoryType,
    ReminderRecord,
    RiskLevel,
    SchedulerTickPayload,
    SchedulerTickResult,
    SelfProfile,
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
    EventRepository,
    ExecutionRunRepository,
    MemoryRepository,
    RelationRepository,
    SelfRepository,
    TaskRepository,
)


class RelationService:
    def __init__(self, repo: RelationRepository, events: EventRepository) -> None:
        self.repo = repo
        self.events = events

    def link(
        self,
        source_type: str,
        source_id: str,
        relation_type: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, object] | None = None,
    ) -> EntityRelation:
        relation = EntityRelation(
            id=str(uuid4()),
            source_type=source_type,
            source_id=source_id,
            relation_type=relation_type,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )
        self.events.append("relation.created", relation.model_dump(mode="json"))
        return self.repo.create(relation)

    def list_for_entity(self, entity_type: str, entity_id: str, limit: int = 100) -> list[EntityRelation]:
        return self.repo.list_for_entity(entity_type, entity_id, limit)


class ExecutionRunService:
    def __init__(self, repo: ExecutionRunRepository, events: EventRepository, relations: RelationService) -> None:
        self.repo = repo
        self.events = events
        self.relations = relations

    def start(self, task_id: str, metadata: dict[str, object] | None = None) -> ExecutionRunRecord:
        run = ExecutionRunRecord(id=str(uuid4()), task_id=task_id, status="executing", metadata=metadata or {})
        saved = self.repo.create(run)
        self.events.append("execution_run.started", saved.model_dump(mode="json"))
        self.relations.link("task", task_id, "spawned_run", "execution_run", saved.id)
        return saved

    def latest_for_task(self, task_id: str) -> ExecutionRunRecord | None:
        return self.repo.latest_for_task(task_id)

    def list_for_task(self, task_id: str, limit: int = 100) -> list[ExecutionRunRecord]:
        return self.repo.list_for_task(task_id, limit)

    def complete(self, run_id: str, status: str, metadata: dict[str, object] | None = None) -> ExecutionRunRecord:
        run = self.repo.get(run_id)
        if not run:
            raise ValueError(f"Execution run {run_id} not found.")
        run.status = status
        run.completed_at = utc_now()
        if metadata:
            run.metadata = {**run.metadata, **metadata}
        saved = self.repo.update(run)
        self.events.append("execution_run.completed", saved.model_dump(mode="json"))
        return saved


class SelfKernel:
    def __init__(self, repo: SelfRepository, events: EventRepository) -> None:
        self.repo = repo
        self.events = events

    def get(self) -> SelfProfile:
        return self.repo.load()

    def update(self, profile: SelfProfile) -> SelfProfile:
        previous = self.repo.load()
        profile.updated_at = utc_now()
        saved = self.repo.save(profile)
        changes = self._diff_profiles(previous, saved)
        self.events.append(
            "self.updated",
            {
                "changes": changes,
                "updated_at": saved.updated_at.isoformat(),
                "current_phase": saved.current_phase,
            },
        )
        return saved

    @staticmethod
    def _diff_profiles(previous: SelfProfile, current: SelfProfile) -> dict[str, dict[str, object]]:
        diff: dict[str, dict[str, object]] = {}
        previous_data = previous.model_dump(mode="json")
        current_data = current.model_dump(mode="json")
        for key, new_value in current_data.items():
            old_value = previous_data.get(key)
            if old_value != new_value and key != "updated_at":
                diff[key] = {"from": old_value, "to": new_value}
        return diff


class MemoryEngine:
    def __init__(self, repo: MemoryRepository, events: EventRepository, relations: RelationService) -> None:
        self.repo = repo
        self.events = events
        self.relations = relations

    def create(self, payload: MemoryCreatePayload) -> MemoryRecord:
        record = MemoryRecord(id=str(uuid4()), **payload.model_dump())
        self.events.append("memory.created", record.model_dump(mode="json"))
        return self.repo.create(record)

    def list(self) -> list[MemoryRecord]:
        return self.repo.list()

    def reflect_task(self, task: TaskRecord, payload: TaskReflectionPayload) -> MemoryRecord:
        content = payload.summary
        if payload.lessons:
            content = f"{content}\nLessons:\n- " + "\n- ".join(payload.lessons)
        record = MemoryRecord(
            id=str(uuid4()),
            memory_type=MemoryType.REFLECTION,
            title=f"Reflection for task {task.id}",
            content=content,
            tags=["task_reflection", task.id],
        )
        self.events.append("memory.reflection_created", record.model_dump(mode="json"))
        saved = self.repo.create(record)
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="produced_reflection",
            target_type="memory",
            target_id=saved.id,
        )
        return saved


class GovernanceLayer:
    def assess(self, text: str) -> tuple[RiskLevel, bool, str]:
        lowered = text.lower()
        risky_tokens = {"delete", "remove", "shutdown", "kill", "transfer", "wire"}
        medium_tokens = {"send", "book", "schedule", "buy"}
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
        execution_plan = self._build_execution_plan(execution_mode)
        reflection_style = self._reflection_context_style(intent.goal)
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
            suggested_execution_mode=execution_mode,
            suggested_execution_plan=execution_plan,
            suggested_task_tags=suggested_task_tags,
            suggested_success_criteria=success_criteria,
            suggested_next_step=next_step,
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
    def _build_execution_plan(mode: ExecutionMode) -> ExecutionPlan:
        if mode == ExecutionMode.MEMORY_CAPTURE:
            return ExecutionPlan(
                mode=mode,
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
        return ExecutionPlan(
            mode=mode,
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
            urgency=4 if any(token in lowered for token in ("urgent", "asap", "today")) else 3,
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
        task_data["execution_mode"] = mode
        task_data["execution_plan"] = payload.execution_plan or self.build_execution_plan(mode)
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
        task.execution_plan = self.build_execution_plan(task.execution_mode)
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
        if any(token in lowered for token in ("remember", "capture", "log", "record note")):
            return ExecutionMode.MEMORY_CAPTURE
        if any(token in lowered for token in ("remind", "schedule", "follow up tomorrow", "later today")):
            return ExecutionMode.REMINDER
        if any(token in lowered for token in ("message", "notify", "email", "text ")):
            return ExecutionMode.MESSAGE_DRAFT
        return ExecutionMode.FILE_ARTIFACT

    @staticmethod
    def build_execution_plan(mode: ExecutionMode) -> ExecutionPlan:
        return CognitionEngine._build_execution_plan(mode)


class CapabilityHandler(Protocol):
    descriptor: CapabilityDescriptor

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult: ...


class NotesCapability:
    descriptor = CapabilityDescriptor(
        name="notes",
        description="Create a lightweight note payload that can later be routed to files or a notes app.",
        risk_level=RiskLevel.LOW,
    )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        title = str(payload.parameters.get("title", "Untitled"))
        body = str(payload.parameters.get("body", ""))
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=f"Prepared note '{title}' with {len(body)} characters.",
        )


class MessagingCapability:
    descriptor = CapabilityDescriptor(
        name="messaging",
        description="Prepare outbound messages while enforcing confirmation for delivery.",
        risk_level=RiskLevel.HIGH,
    )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        recipient = str(payload.parameters.get("recipient", "unknown"))
        message = str(payload.parameters.get("message", ""))
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="pending_confirmation",
            output=f"Message to {recipient} prepared with {len(message)} characters.",
            requires_confirmation=True,
        )


class RemindersCapability:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.store_path = self.workspace_root / ".ai_os" / "reminders.json"
        self.descriptor = CapabilityDescriptor(
            name="reminders",
            description="Create and inspect local reminder entries stored inside the workspace.",
            risk_level=RiskLevel.LOW,
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        reminders = self._load()
        if payload.action == "create":
            due_hint = str(payload.parameters.get("due_hint", "unspecified"))
            reminder = ReminderRecord(
                id=str(uuid4()),
                title=str(payload.parameters.get("title", "Untitled reminder")),
                note=str(payload.parameters.get("note", "")),
                due_hint=due_hint,
                scheduled_for=self._resolve_schedule(
                    due_hint=due_hint,
                    explicit_scheduled_for=payload.parameters.get("scheduled_for"),
                ),
                source_task_id=str(payload.parameters["source_task_id"]) if payload.parameters.get("source_task_id") else None,
                origin=str(payload.parameters["origin"]) if payload.parameters.get("origin") else None,
            )
            reminders.append(reminder)
            self._save(reminders)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps(reminder.model_dump(mode="json")),
            )
        if payload.action == "list":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps([reminder.model_dump(mode="json") for reminder in reminders]),
            )
        if payload.action == "delete":
            reminder_id = str(payload.parameters.get("id", ""))
            filtered = [item for item in reminders if item.id != reminder_id]
            self._save(filtered)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder removed: {reminder_id}",
            )
        if payload.action == "reschedule":
            reminder_id = str(payload.parameters.get("id", ""))
            due_hint = str(payload.parameters.get("due_hint", "rescheduled"))
            scheduled_for = self._resolve_schedule(
                due_hint=due_hint,
                explicit_scheduled_for=payload.parameters.get("scheduled_for"),
            )
            origin = str(payload.parameters["origin"]) if payload.parameters.get("origin") else None
            updated_count = 0
            updated: list[ReminderRecord] = []
            for reminder in reminders:
                if reminder.id == reminder_id:
                    update = {"due_hint": due_hint, "scheduled_for": scheduled_for, "last_seen_at": None}
                    if origin:
                        update["origin"] = origin
                    reminder = reminder.model_copy(update=update)
                    updated_count += 1
                updated.append(reminder)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder rescheduled: {reminder_id} ({updated_count})",
            )
        if payload.action == "mark_seen":
            reminder_id = str(payload.parameters.get("id", ""))
            marked_count = 0
            marked_at = self._parse_datetime(payload.parameters.get("seen_at")) or utc_now()
            updated: list[ReminderRecord] = []
            for reminder in reminders:
                if reminder.id == reminder_id:
                    reminder = reminder.model_copy(update={"last_seen_at": marked_at})
                    marked_count += 1
                updated.append(reminder)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder marked seen: {reminder_id} ({marked_count})",
            )
        raise ValueError(f"Unsupported reminders action: {payload.action}")

    def _load(self) -> list[ReminderRecord]:
        if not self.store_path.exists():
            return []
        raw_items = json.loads(self.store_path.read_text(encoding="utf-8"))
        return [ReminderRecord.model_validate(item) for item in raw_items]

    def _save(self, reminders: list[ReminderRecord]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [reminder.model_dump(mode="json") for reminder in reminders]
        self.store_path.write_text(json.dumps(serialized, ensure_ascii=True, indent=2), encoding="utf-8")

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        return datetime.fromisoformat(value)

    @classmethod
    def _resolve_schedule(cls, due_hint: str, explicit_scheduled_for: object) -> datetime:
        if parsed := cls._parse_datetime(explicit_scheduled_for):
            return parsed

        lowered = due_hint.lower()
        now = utc_now()
        if "later today" in lowered:
            return now + timedelta(hours=4)
        if "tomorrow" in lowered or "next review cycle" in lowered:
            return now + timedelta(days=1)
        if "next week" in lowered or "weekly" in lowered:
            return now + timedelta(days=7)
        return now


class LocalFilesCapability:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.descriptor = CapabilityDescriptor(
            name="local_files",
            description="Read, write, and inspect files inside the workspace root only.",
            risk_level=RiskLevel.MEDIUM,
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        target = self._resolve_target(str(payload.parameters.get("path", "")))
        if payload.action == "write_text":
            content = str(payload.parameters.get("content", ""))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Wrote {len(content)} characters to {target.relative_to(self.workspace_root)}.",
            )
        if payload.action == "read_text":
            if not target.exists():
                raise ValueError(f"File {target.relative_to(self.workspace_root)} does not exist.")
            content = target.read_text(encoding="utf-8")
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=content,
            )
        if payload.action == "list_dir":
            directory = target if target.suffix == "" or target.is_dir() else target.parent
            if not directory.exists():
                raise ValueError(f"Directory {directory.relative_to(self.workspace_root)} does not exist.")
            entries = sorted(path.name for path in directory.iterdir())
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps(entries),
            )
        if payload.action == "exists":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output="true" if target.exists() else "false",
            )
        raise ValueError(f"Unsupported local_files action: {payload.action}")

    def _resolve_target(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("Capability local_files requires a path parameter.")
        candidate = (self.workspace_root / raw_path).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("Path escapes the workspace root.") from exc
        return candidate


class CapabilityBus:
    def __init__(self, workspace_root: Path) -> None:
        self._handlers: dict[str, CapabilityHandler] = {
            "local_files": LocalFilesCapability(workspace_root),
            "reminders": RemindersCapability(workspace_root),
            "notes": NotesCapability(),
            "messaging": MessagingCapability(),
        }

    def list(self) -> list[CapabilityDescriptor]:
        return [handler.descriptor for handler in self._handlers.values()]

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        handler = self._handlers.get(payload.capability_name)
        if not handler:
            raise ValueError(f"Capability {payload.capability_name} is not registered.")
        return handler.execute(payload)


@dataclass
class KernelContainer:
    self_kernel: SelfKernel
    intent_engine: IntentEngine
    cognition_engine: CognitionEngine
    memory_engine: MemoryEngine
    relation_service: RelationService
    execution_run_service: ExecutionRunService
    task_engine: TaskEngine
    capability_bus: CapabilityBus
    event_repo: EventRepository
    scheduler_service: SchedulerService


def build_container(data_dir: Path) -> KernelContainer:
    workspace_root = data_dir if data_dir.is_dir() else data_dir.parent
    db = Database(data_dir / "ai_os.db")
    events = EventRepository(db)
    self_repo = SelfRepository(db)
    memory_repo = MemoryRepository(db)
    relation_repo = RelationRepository(db)
    execution_run_repo = ExecutionRunRepository(db)
    task_repo = TaskRepository(db)
    governance = GovernanceLayer()
    relation_service = RelationService(relation_repo, events)
    execution_run_service = ExecutionRunService(execution_run_repo, events, relation_service)
    self_kernel = SelfKernel(self_repo, events)
    intent_engine = IntentEngine(governance)
    memory_engine = MemoryEngine(memory_repo, events, relation_service)
    cognition_engine = CognitionEngine(memory_engine=memory_engine)
    task_engine = TaskEngine(task_repo, events)
    capability_bus = CapabilityBus(workspace_root)
    candidate_service = CandidateTaskService(
        self_kernel=self_kernel,
        task_engine=task_engine,
        event_repo=events,
        capability_bus=capability_bus,
        relation_service=relation_service,
    )
    delivery = DeliveryCoordinator(
        task_engine=task_engine,
        memory_engine=memory_engine,
        capability_bus=capability_bus,
        relation_service=relation_service,
        execution_run_service=execution_run_service,
    )
    scheduler_service = SchedulerService(
        candidate_service, task_engine, delivery, events, self_kernel, relation_service, memory_engine
    )

    return KernelContainer(
        self_kernel=self_kernel,
        intent_engine=intent_engine,
        cognition_engine=cognition_engine,
        memory_engine=memory_engine,
        relation_service=relation_service,
        execution_run_service=execution_run_service,
        task_engine=task_engine,
        capability_bus=capability_bus,
        event_repo=events,
        scheduler_service=scheduler_service,
    )


class IntakeCoordinator:
    def __init__(
        self,
        self_kernel: SelfKernel,
        intent_engine: IntentEngine,
        cognition_engine: CognitionEngine,
        task_engine: TaskEngine,
    ) -> None:
        self.self_kernel = self_kernel
        self.intent_engine = intent_engine
        self.cognition_engine = cognition_engine
        self.task_engine = task_engine

    def process(self, payload: InputPayload) -> IntakeResponse:
        profile = self.self_kernel.get()
        intent = self.intent_engine.evaluate(payload, profile)
        cognition = self.cognition_engine.analyze(intent, profile)
        task = self.task_engine.ensure_from_intent(intent, cognition)
        return IntakeResponse(intent=intent, cognition=cognition, task=task)


class DeliveryCoordinator:
    def __init__(
        self,
        task_engine: TaskEngine,
        memory_engine: MemoryEngine,
        capability_bus: CapabilityBus,
        relation_service: RelationService,
        execution_run_service: ExecutionRunService,
    ) -> None:
        self.task_engine = task_engine
        self.memory_engine = memory_engine
        self.capability_bus = capability_bus
        self.relations = relation_service
        self.execution_runs = execution_run_service

    def execute_capability(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        return self.capability_bus.execute(payload)

    def execute_task(self, task_id: str) -> TaskRecord:
        task = self.task_engine.mark_executing(task_id)
        run = self.execution_runs.start(task.id, metadata={"execution_mode": task.execution_mode.value})
        executor_name = task.execution_plan.mode.value
        if task.execution_plan.mode == ExecutionMode.MEMORY_CAPTURE:
            self._execute_memory_capture(task, run.id)
        elif task.execution_plan.mode == ExecutionMode.REMINDER:
            self._execute_reminder(task, run.id)
        elif task.execution_plan.mode == ExecutionMode.MESSAGE_DRAFT:
            self._execute_message_draft(task, run.id)
        else:
            self._execute_file_artifact(task, run.id)

        task.updated_at = utc_now()
        self.task_engine.events.append(
            "task.executed",
            {"task_id": task.id, "execution_run_id": run.id, "executor": executor_name, "artifact_paths": task.artifact_paths},
        )
        return self.task_engine.repo.update(task)

    def verify_task(self, task_id: str, payload: TaskVerificationPayload) -> TaskRecord:
        task = self.task_engine.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        checks = list(payload.checks)
        checks.extend(self._collect_expected_evidence(task))
        enriched_payload = TaskVerificationPayload(checks=checks, verifier_notes=payload.verifier_notes)
        verified = self.task_engine.verify(task_id, enriched_payload)
        if run := self.execution_runs.latest_for_task(task_id):
            self.relations.link(
                "execution_run",
                run.id,
                "produced_verification",
                "task",
                task_id,
                metadata={"status": verified.status.value},
            )
            if verified.status in {TaskStatus.DONE, TaskStatus.BLOCKED}:
                self.execution_runs.complete(run.id, verified.status.value, metadata={"task_status": verified.status.value})
        return verified

    def confirm_task(self, task_id: str, payload: TaskConfirmationPayload) -> TaskRecord:
        task = self.task_engine.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if task.execution_plan.mode != ExecutionMode.MESSAGE_DRAFT:
            raise ValueError("Task confirmation is only supported for message draft tasks.")
        if task.status != TaskStatus.BLOCKED:
            raise ValueError(f"Cannot confirm task from {task.status.value}.")

        note = payload.note or ("User approved message delivery." if payload.approved else "User rejected message delivery.")
        task.verification_notes.append(note)
        if payload.approved:
            task.status = TaskStatus.EXECUTING
            task.blocker_reason = None
            self.task_engine.events.append("task.confirmed", {"task_id": task.id, "approved": True, "note": note})
        else:
            task.status = TaskStatus.ARCHIVED
            task.blocker_reason = "User rejected message delivery."
            self.task_engine.events.append("task.confirmed", {"task_id": task.id, "approved": False, "note": note})
        task.updated_at = utc_now()
        return self.task_engine.repo.update(task)

    def reflect_task(self, task_id: str, payload: TaskReflectionPayload) -> MemoryRecord:
        task = self.task_engine.repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if task.status != TaskStatus.DONE:
            raise ValueError("Task must be done before reflection is stored.")
        reflection = self.memory_engine.reflect_task(task, payload)
        if run := self.execution_runs.latest_for_task(task_id):
            self.relations.link("execution_run", run.id, "produced_reflection", "memory", reflection.id)
        return reflection

    @staticmethod
    def _artifact_path_for(task: TaskRecord) -> str:
        safe_slug = "".join(char.lower() if char.isalnum() else "-" for char in task.objective).strip("-")
        safe_slug = "-".join(part for part in safe_slug.split("-") if part) or task.id
        return f"artifacts/tasks/{task.id}-{safe_slug[:48]}.md"

    @staticmethod
    def _render_task_artifact(task: TaskRecord) -> str:
        lines = [
            f"# Task Plan: {task.objective}",
            "",
            f"- Task ID: {task.id}",
            f"- Status: {task.status.value}",
            f"- Risk: {task.risk_level.value}",
            f"- Execution Mode: {task.execution_mode.value}",
            "",
            "## Execution Plan",
        ]
        lines.extend([f"- {step.capability_name}:{step.action} -> {step.purpose}" for step in task.execution_plan.steps])
        lines.extend([
            "",
            "## Success Criteria",
        ])
        if task.success_criteria:
            lines.extend([f"- {criterion}" for criterion in task.success_criteria])
        else:
            lines.append("- No explicit success criteria recorded yet.")
        lines.extend(["", "## Subtasks"])
        if task.subtasks:
            lines.extend([f"- {step}" for step in task.subtasks])
        else:
            lines.append("- No subtasks planned yet.")
        return "\n".join(lines)

    def _execute_file_artifact(self, task: TaskRecord, run_id: str) -> None:
        artifact_path = self._artifact_path_for(task)
        plan_content = self._render_task_artifact(task)
        self.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="write_text",
                parameters={"path": artifact_path, "content": plan_content},
            )
        )
        task.artifact_paths = sorted({*task.artifact_paths, artifact_path})
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="produced_artifact",
            target_type="artifact",
            target_id=artifact_path,
            metadata={"path": artifact_path},
        )
        self.relations.link("execution_run", run_id, "produced_artifact", "artifact", artifact_path, metadata={"path": artifact_path})

    def _execute_memory_capture(self, task: TaskRecord, run_id: str) -> None:
        record = self.memory_engine.create(
            MemoryCreatePayload(
                memory_type=MemoryType.KNOWLEDGE,
                title=task.objective,
                content=f"Captured from task {task.id}: {task.objective}",
                tags=["task_capture", task.id],
            )
        )
        task.verification_notes.append(f"Memory created: {record.id}")
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="captured_into_memory",
            target_type="memory",
            target_id=record.id,
        )
        self.relations.link("execution_run", run_id, "captured_into_memory", "memory", record.id)

    def _execute_message_draft(self, task: TaskRecord, run_id: str) -> None:
        result = self.execute_capability(
            CapabilityExecutionPayload(
                capability_name="messaging",
                action="prepare",
                parameters={"recipient": "pending", "message": task.objective},
            )
        )
        task.verification_notes.append(result.output)
        self.relations.link(
            "execution_run",
            run_id,
            "prepared_message",
            "task",
            task.id,
            metadata={"message_preview": task.objective},
        )
        if result.requires_confirmation:
            task.status = TaskStatus.BLOCKED
            task.blocker_reason = "Awaiting user confirmation to send drafted message."

    def _execute_reminder(self, task: TaskRecord, run_id: str) -> None:
        result = self.execute_capability(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="create",
                parameters={
                    "title": task.objective,
                    "note": f"Created from task {task.id}",
                    "due_hint": "next review cycle",
                    "scheduled_for": (utc_now() + timedelta(days=1)).isoformat(),
                    "source_task_id": task.id,
                    "origin": "task_engine",
                },
            )
        )
        reminder = ReminderRecord.model_validate_json(result.output)
        task.verification_notes.append(f"Reminder scheduled: {reminder.id}")
        reminder_id = reminder.id
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="scheduled_reminder",
            target_type="reminder",
            target_id=reminder_id,
        )
        self.relations.link("execution_run", run_id, "scheduled_reminder", "reminder", reminder_id)

    def _collect_expected_evidence(self, task: TaskRecord) -> list[str]:
        evidence_notes: list[str] = []
        for evidence in task.execution_plan.expected_evidence:
            normalized = evidence.lower()
            if normalized == "task artifact file exists":
                evidence_notes.extend(self._artifact_evidence(task))
            elif normalized == "memory record created":
                evidence_notes.append(self._memory_evidence(task))
            elif normalized == "drafted outbound message":
                evidence_notes.append(self._message_draft_evidence(task))
            elif normalized == "user confirmation pending or complete":
                evidence_notes.append(self._message_confirmation_evidence(task))
            elif normalized == "reminder scheduled":
                evidence_notes.append(self._reminder_evidence(task))
            else:
                evidence_notes.append(f"Unverified expected evidence: {evidence}")
        return evidence_notes

    def _artifact_evidence(self, task: TaskRecord) -> list[str]:
        notes: list[str] = []
        for artifact_path in task.artifact_paths:
            exists_result = self.execute_capability(
                CapabilityExecutionPayload(
                    capability_name="local_files",
                    action="exists",
                    parameters={"path": artifact_path},
                )
            )
            if exists_result.output == "true":
                notes.append(f"Artifact exists: {artifact_path}")
            else:
                notes.append(f"Missing artifact: {artifact_path}")
        if not notes:
            notes.append("Missing artifact: no artifact paths recorded")
        return notes

    @staticmethod
    def _memory_evidence(task: TaskRecord) -> str:
        if any(note.startswith("Memory created:") for note in task.verification_notes):
            return "Memory record created"
        return "Missing memory record created evidence"

    @staticmethod
    def _message_draft_evidence(task: TaskRecord) -> str:
        if any("prepared" in note.lower() and "message" in note.lower() for note in task.verification_notes):
            return "Drafted outbound message"
        return "Missing drafted outbound message evidence"

    @staticmethod
    def _message_confirmation_evidence(task: TaskRecord) -> str:
        if task.blocker_reason == "Awaiting user confirmation to send drafted message.":
            return "Missing user confirmation evidence"
        if task.status in {TaskStatus.DONE, TaskStatus.EXECUTING} and any(
            "approved message delivery" in note.lower() for note in task.verification_notes
        ):
            return "User confirmation pending or complete"
        return "Missing user confirmation evidence"

    @staticmethod
    def _reminder_evidence(task: TaskRecord) -> str:
        if any(note.lower().startswith("reminder scheduled:") for note in task.verification_notes):
            return "Reminder scheduled"
        return "Missing reminder scheduled evidence"


class EventQueryService:
    def __init__(self, event_repo: EventRepository) -> None:
        self.event_repo = event_repo

    def list_recent(self, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_recent(limit)

    def list_for_task(self, task_id: str, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_for_task(task_id, limit)

    def list_for_execution_run(self, run_id: str, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_for_execution_run(run_id, limit)

    def task_timeline(self, task_id: str, limit: int = 100) -> list[TimelineItem]:
        events = self.event_repo.list_for_task(task_id, limit)
        return [self._to_timeline_item(event) for event in reversed(events)]

    def execution_run_timeline(self, run_id: str, limit: int = 100) -> list[TimelineItem]:
        events = self.event_repo.list_for_execution_run(run_id, limit)
        return [self._to_timeline_item(event) for event in reversed(events)]

    def self_timeline(self, limit: int = 100) -> list[TimelineItem]:
        events = [event for event in self.event_repo.list_recent(limit * 3) if event.event_type == "self.updated"][:limit]
        return [self._to_timeline_item(event) for event in reversed(events)]

    @staticmethod
    def _to_timeline_item(event: EventRecord) -> TimelineItem:
        payload = event.payload
        mapping = {
            "task.created": ("captured", "Task Captured", payload.get("objective", "Task created")),
            "task.planned": ("planned", "Task Planned", f"Execution mode: {payload.get('execution_mode', 'unknown')}"),
            "task.executing": ("executing", "Execution Started", "Task moved into execution."),
            "task.executed": ("executing", "Execution Produced Output", EventQueryService._execution_detail(payload)),
            "task.resumed_from_reminder": ("coordination", "Reminder Resumed Task", EventQueryService._reminder_resume_detail(payload)),
            "task.confirmed": ("confirmed", "User Decision Recorded", EventQueryService._confirmation_detail(payload)),
            "task.verified": ("verified", "Verification Completed", f"Status: {payload.get('status', 'unknown')}"),
            "candidate.accepted": ("coordination", "Candidate Accepted", EventQueryService._candidate_detail(payload)),
            "candidate.auto_accepted": ("coordination", "Candidate Auto-Accepted", EventQueryService._candidate_detail(payload)),
            "candidate.auto_accept_batch_completed": ("coordination", "Candidate Auto-Accept Batch Completed", EventQueryService._candidate_batch_detail(payload)),
            "candidate.deferred": ("coordination", "Candidate Deferred", EventQueryService._candidate_defer_detail(payload)),
            "scheduler.stalled_task.escalated": ("coordination", "Stalled Task Escalated", EventQueryService._stalled_escalation_detail(payload)),
            "scheduler.stalled_task.followup_created": ("coordination", "Stalled Task Follow-Up Created", EventQueryService._stalled_followup_detail(payload)),
            "scheduler.stalled_task.reminder_created": ("coordination", "Stalled Task Reminder Created", EventQueryService._stalled_task_detail(payload)),
            "scheduler.tick.completed": ("coordination", "Scheduler Tick Completed", EventQueryService._scheduler_tick_detail(payload)),
            "execution_run.started": ("run", "Execution Run Started", EventQueryService._run_detail(payload)),
            "execution_run.completed": ("run", "Execution Run Completed", EventQueryService._run_completion_detail(payload)),
            "memory.created": ("memory", "Memory Stored", payload.get("title", "Memory created")),
            "memory.reflection_created": ("reflection", "Reflection Stored", payload.get("title", "Reflection created")),
            "relation.created": ("relation", "Relation Recorded", EventQueryService._relation_detail(payload)),
            "self.updated": ("self", "Self Profile Updated", EventQueryService._self_detail(payload)),
        }
        phase, title, detail = mapping.get(
            event.event_type,
            ("event", event.event_type.replace(".", " ").title(), json.dumps(payload, ensure_ascii=True)),
        )
        return TimelineItem(
            timestamp=event.created_at,
            phase=phase,
            title=title,
            detail=detail,
            event_type=event.event_type,
        )

    @staticmethod
    def _execution_detail(payload: dict) -> str:
        artifact_paths = payload.get("artifact_paths") or []
        if artifact_paths:
            return f"Artifacts: {', '.join(artifact_paths)}"
        executor = payload.get("executor", "unknown")
        return f"Executor: {executor}"

    @staticmethod
    def _confirmation_detail(payload: dict) -> str:
        if payload.get("approved"):
            return payload.get("note", "User approved the task.")
        return payload.get("note", "User rejected the task.")

    @staticmethod
    def _self_detail(payload: dict) -> str:
        changes = payload.get("changes", {})
        if not changes:
            return "Self profile saved with no material field changes."
        changed_fields = ", ".join(sorted(changes.keys()))
        return f"Changed fields: {changed_fields}"

    @staticmethod
    def _relation_detail(payload: dict) -> str:
        return (
            f"{payload.get('source_type')}:{payload.get('source_id')} "
            f"{payload.get('relation_type')} "
            f"{payload.get('target_type')}:{payload.get('target_id')}"
        )

    @staticmethod
    def _run_detail(payload: dict) -> str:
        return f"Run {payload.get('id')} started for task {payload.get('task_id')}."

    @staticmethod
    def _run_completion_detail(payload: dict) -> str:
        return f"Run {payload.get('id')} completed with status {payload.get('status', 'unknown')}."

    @staticmethod
    def _candidate_detail(payload: dict) -> str:
        kind = payload.get("kind", "unknown")
        action = payload.get("action", "accepted")
        reason_code = payload.get("reason_code", "unspecified")
        trigger_source = payload.get("trigger_source", "system")
        return f"Accepted {kind} candidate with action {action} ({reason_code} via {trigger_source})."

    @staticmethod
    def _candidate_defer_detail(payload: dict) -> str:
        due_hint = payload.get("due_hint", "later")
        reason_code = payload.get("reason_code", "unspecified")
        return f"Deferred candidate until {due_hint} ({reason_code})."

    @staticmethod
    def _candidate_batch_detail(payload: dict) -> str:
        skip_counts = EventQueryService._skip_reason_summary(payload)
        return (
            f"Accepted {payload.get('accepted_count', 0)}, "
            f"skipped {payload.get('skipped_count', 0)}, "
            f"errors {payload.get('error_count', 0)}"
            + (f", skip reasons: {skip_counts}." if skip_counts else ".")
        )

    @staticmethod
    def _scheduler_tick_detail(payload: dict) -> str:
        skip_counts = EventQueryService._skip_reason_summary(payload)
        return (
            f"Discovered {payload.get('discovered_count', 0)}, "
            f"auto-accepted {payload.get('auto_accepted_count', 0)}, "
            f"auto-started {payload.get('auto_started_count', 0)}, "
            f"auto-verified {payload.get('auto_verified_count', 0)}, "
            f"blocked follow-ups {payload.get('blocked_followup_count', 0)}, "
            f"stalled reminders {payload.get('stalled_reminder_count', 0)}, "
            f"escalations {payload.get('escalated_count', 0)}, "
            f"skipped {payload.get('skipped_count', 0)}, "
            f"errors {payload.get('error_count', 0)}"
            + (f", skip reasons: {skip_counts}." if skip_counts else ".")
        )

    @staticmethod
    def _skip_reason_summary(payload: dict) -> str:
        skip_reason_counts = payload.get("skip_reason_counts", {})
        if not skip_reason_counts:
            return ""
        return ", ".join(
            f"{reason}={count}" for reason, count in sorted(skip_reason_counts.items())
        )

    @staticmethod
    def _stalled_task_detail(payload: dict) -> str:
        return f"Created reminder for stalled task {payload.get('task_id')} after {payload.get('stale_after_minutes', 'unknown')} minutes."

    @staticmethod
    def _stalled_followup_detail(payload: dict) -> str:
        return (
            f"Created follow-up {payload.get('followup_task_id')} for blocked task "
            f"{payload.get('task_id')} after {payload.get('stale_after_minutes', 'unknown')} minutes."
        )

    @staticmethod
    def _stalled_escalation_detail(payload: dict) -> str:
        actions = ", ".join(payload.get("actions", [])) or "no actions recorded"
        return (
            f"Escalated stalled task {payload.get('task_id')} via {payload.get('policy_name', 'default_policy')} "
            f"after {payload.get('escalate_after_hits', 'unknown')} hits: {actions}."
        )

    @staticmethod
    def _reminder_resume_detail(payload: dict) -> str:
        action = payload.get("action", "resumed_existing_task")
        reminder_id = payload.get("reminder_id", "unknown")
        return f"Reminder {reminder_id} resumed task via {action}."


class CandidateTaskService:
    POLICY_MAP: dict[str, dict[str, object]] = {
        "blocked_task": {"priority": 5, "auto_acceptable": False, "needs_confirmation": True},
        "executing_follow_up": {"priority": 4, "auto_acceptable": True, "needs_confirmation": False},
        "captured_task": {"priority": 3, "auto_acceptable": True, "needs_confirmation": False},
        "needs_confirmation_gate": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "governance_review": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "empty_phase": {"priority": 2, "auto_acceptable": False, "needs_confirmation": False},
        "phase_change": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "due_reminder": {"priority": 4, "auto_acceptable": True, "needs_confirmation": False},
    }

    def __init__(
        self,
        self_kernel: SelfKernel,
        task_engine: TaskEngine,
        event_repo: EventRepository,
        capability_bus: CapabilityBus,
        relation_service: RelationService,
    ) -> None:
        self.self_kernel = self_kernel
        self.task_engine = task_engine
        self.event_repo = event_repo
        self.capability_bus = capability_bus
        self.relations = relation_service

    def discover(self, limit: int = 10) -> list[CandidateTask]:
        now = utc_now()
        profile = self.self_kernel.get()
        tasks = self.task_engine.list()
        candidates: list[CandidateTask] = []

        for task in tasks:
            if task.status == TaskStatus.BLOCKED:
                policy = self._policy_for_task_candidate(task, "blocked_task")
                candidates.append(
                    CandidateTask(
                        kind="unblock",
                        title=f"Unblock: {task.objective}",
                        detail=task.blocker_reason or "Task is blocked and needs intervention.",
                        source_task_id=task.id,
                        reason_code="blocked_task",
                        trigger_source="task_status",
                        priority=policy["priority"],
                        auto_acceptable=policy["auto_acceptable"],
                        needs_confirmation=policy["needs_confirmation"],
                    )
                )
                candidates.extend(self._governance_candidates_for_task(task))
            elif task.status == TaskStatus.EXECUTING:
                policy = self._policy_for_task_candidate(task, "executing_follow_up")
                candidates.append(
                    CandidateTask(
                        kind="follow_up",
                        title=f"Verify progress: {task.objective}",
                        detail="Task is in execution and should be verified or advanced.",
                        source_task_id=task.id,
                        reason_code="executing_follow_up",
                        trigger_source="task_status",
                        priority=policy["priority"],
                        auto_acceptable=policy["auto_acceptable"],
                        needs_confirmation=policy["needs_confirmation"],
                    )
                )
                candidates.extend(self._governance_candidates_for_task(task))
            elif task.status == TaskStatus.CAPTURED:
                policy = self._policy_for_task_candidate(task, "captured_task")
                candidates.append(
                    CandidateTask(
                        kind="plan",
                        title=f"Plan: {task.objective}",
                        detail="Captured task has not been planned yet.",
                        source_task_id=task.id,
                        reason_code="captured_task",
                        trigger_source="task_status",
                        priority=policy["priority"],
                        auto_acceptable=policy["auto_acceptable"],
                        needs_confirmation=policy["needs_confirmation"],
                    )
                )
                candidates.extend(self._governance_candidates_for_task(task))

        if profile.current_phase and not tasks:
            policy = self._policy_for("empty_phase")
            candidates.append(
                CandidateTask(
                    kind="bootstrap",
                    title=f"Define work for phase: {profile.current_phase}",
                    detail="No active tasks exist for the current self phase.",
                    reason_code="empty_phase",
                    trigger_source="self_profile",
                    priority=policy["priority"],
                    auto_acceptable=policy["auto_acceptable"],
                    needs_confirmation=policy["needs_confirmation"],
                )
            )

        recent_self_events = [event for event in self.event_repo.list_recent(limit=20) if event.event_type == "self.updated"]
        if recent_self_events:
            latest_self = recent_self_events[0]
            changes = latest_self.payload.get("changes", {})
            if "current_phase" in changes:
                new_phase = changes["current_phase"].get("to")
                policy = self._policy_for("phase_change")
                candidates.append(
                    CandidateTask(
                        kind="phase_alignment",
                        title=f"Align tasks with phase: {new_phase}",
                        detail="Self phase changed recently; review active tasks for alignment.",
                        reason_code="phase_change",
                        trigger_source="self_event",
                        priority=policy["priority"],
                        auto_acceptable=policy["auto_acceptable"],
                        needs_confirmation=policy["needs_confirmation"],
                    )
                )

        reminders = json.loads(
            self.capability_bus.execute(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        due_reminders: list[dict] = []
        for reminder in reminders:
            if not self._is_due_reminder(reminder, now):
                continue
            due_reminders.append(reminder)
            source_task = self.task_engine.repo.get(reminder.get("source_task_id")) if reminder.get("source_task_id") else None
            policy = self._policy_for_task_candidate(source_task, "due_reminder")
            candidates.append(
                CandidateTask(
                    kind="reminder_due",
                    title=f"Resume reminder: {reminder.get('title', 'Untitled reminder')}",
                    detail=reminder.get("note", "Reminder needs follow-up."),
                    source_task_id=reminder.get("source_task_id"),
                    reason_code="due_reminder",
                    trigger_source="reminder_schedule",
                    metadata={
                        "reminder_id": reminder.get("id"),
                        "due_hint": reminder.get("due_hint", "unspecified"),
                        "scheduled_for": reminder.get("scheduled_for"),
                        "source_task_id": reminder.get("source_task_id"),
                        "origin": reminder.get("origin"),
                    },
                    priority=policy["priority"],
                    auto_acceptable=policy["auto_acceptable"],
                    needs_confirmation=policy["needs_confirmation"],
                )
            )

        for reminder in due_reminders:
            if reminder.get("id"):
                self.capability_bus.execute(
                    CapabilityExecutionPayload(
                        capability_name="reminders",
                        action="mark_seen",
                        parameters={"id": reminder["id"], "seen_at": now.isoformat()},
                    )
                )

        candidates.sort(key=lambda item: item.priority, reverse=True)
        return candidates[:limit]

    @classmethod
    def _policy_for(cls, reason_code: str) -> dict[str, object]:
        return cls.POLICY_MAP.get(
            reason_code,
            {"priority": 3, "auto_acceptable": False, "needs_confirmation": False},
        )

    @classmethod
    def _policy_for_task_candidate(cls, task: TaskRecord | None, reason_code: str) -> dict[str, object]:
        policy = dict(cls._policy_for(reason_code))
        if not task:
            return policy
        tags = set(task.tags)
        cautious = "governance:cautious" in tags or "guardrail:reflection" in tags
        bold = "governance:bold" in tags
        if cautious:
            policy["priority"] = max(int(policy["priority"]), 4)
            policy["auto_acceptable"] = False
            policy["needs_confirmation"] = True
        elif bold and reason_code in {"captured_task", "due_reminder"}:
            policy["auto_acceptable"] = True
            policy["needs_confirmation"] = False
        if task.execution_plan.confirmation_required:
            policy["auto_acceptable"] = False
            policy["needs_confirmation"] = True
            policy["priority"] = max(int(policy["priority"]), 4)
        return policy

    @classmethod
    def _governance_candidates_for_task(cls, task: TaskRecord) -> list[CandidateTask]:
        candidates: list[CandidateTask] = []
        tags = set(task.tags)
        if task.execution_plan.confirmation_required:
            policy = cls._policy_for("needs_confirmation_gate")
            candidates.append(
                CandidateTask(
                    kind="confirm_gate",
                    title=f"Review confirmation gate: {task.objective}",
                    detail="This task requires explicit confirmation before autonomous execution.",
                    source_task_id=task.id,
                    reason_code="needs_confirmation_gate",
                    trigger_source="task_governance",
                    priority=int(policy["priority"]),
                    auto_acceptable=bool(policy["auto_acceptable"]),
                    needs_confirmation=bool(policy["needs_confirmation"]),
                )
            )
        if "governance:cautious" in tags or "guardrail:reflection" in tags:
            policy = cls._policy_for("governance_review")
            candidates.append(
                CandidateTask(
                    kind="governance_review",
                    title=f"Review governance: {task.objective}",
                    detail="Task governance tags currently prevent autonomous advancement.",
                    source_task_id=task.id,
                    reason_code="governance_review",
                    trigger_source="task_governance",
                    priority=int(policy["priority"]),
                    auto_acceptable=bool(policy["auto_acceptable"]),
                    needs_confirmation=bool(policy["needs_confirmation"]),
                )
            )
        return candidates

    def accept(self, payload: CandidateAcceptancePayload) -> CandidateAcceptanceResult:
        if payload.kind == "confirm_gate" and payload.source_task_id:
            task = self.task_engine.repo.get(payload.source_task_id)
            if not task:
                raise ValueError(f"Task {payload.source_task_id} not found.")
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": task.id,
                    "action": "review_confirmation_gate",
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            return CandidateAcceptanceResult(action="review_confirmation_gate", task=task)

        if payload.kind == "governance_review" and payload.source_task_id:
            source = self.task_engine.repo.get(payload.source_task_id)
            if not source:
                raise ValueError(f"Task {payload.source_task_id} not found.")
            created = self.task_engine.create(
                TaskCreatePayload(
                    objective=f"Review governance for: {source.objective}",
                    tags=["governance:review"],
                    success_criteria=["Governance stance is reviewed and the next action is explicit."],
                    risk_level=source.risk_level,
                )
            )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": created.id,
                    "source_task_id": source.id,
                    "action": "created_governance_review_task",
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            return CandidateAcceptanceResult(action="created_governance_review_task", task=created)

        if payload.kind in {"plan", "follow_up"} and payload.source_task_id:
            task = self.task_engine.repo.get(payload.source_task_id)
            if not task:
                raise ValueError(f"Task {payload.source_task_id} not found.")
            if payload.kind == "plan" and task.status == TaskStatus.CAPTURED:
                updated = self.task_engine.plan(task.id)
                self.event_repo.append(
                    "candidate.accepted",
                    {
                        "kind": payload.kind,
                        "task_id": task.id,
                        "action": "planned",
                        "reason_code": payload.reason_code,
                        "trigger_source": payload.trigger_source,
                    },
                )
                return CandidateAcceptanceResult(action="planned_task", task=updated)
            if payload.kind == "follow_up" and task.status == TaskStatus.EXECUTING:
                self.event_repo.append(
                    "candidate.accepted",
                    {
                        "kind": payload.kind,
                        "task_id": task.id,
                        "action": "review_requested",
                        "reason_code": payload.reason_code,
                        "trigger_source": payload.trigger_source,
                    },
                )
                return CandidateAcceptanceResult(action="review_existing_task", task=task)

        if payload.kind == "unblock" and payload.source_task_id:
            source = self.task_engine.repo.get(payload.source_task_id)
            if not source:
                raise ValueError(f"Task {payload.source_task_id} not found.")
            created = self.task_engine.create(
                TaskCreatePayload(
                    objective=f"Resolve blocker: {source.objective}",
                    success_criteria=["Blocker is clarified or removed."],
                    risk_level=source.risk_level,
                )
            )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": created.id,
                    "source_task_id": source.id,
                    "action": "created_unblock_task",
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            return CandidateAcceptanceResult(action="created_unblock_task", task=created)

        if payload.kind == "reminder_due":
            reminder_id = payload.metadata.get("reminder_id")
            source_task_id = payload.source_task_id or payload.metadata.get("source_task_id")
            source_task = self.task_engine.repo.get(source_task_id) if source_task_id else None
            if source_task and source_task.status in {TaskStatus.CAPTURED, TaskStatus.CLARIFYING}:
                updated = self.task_engine.plan(source_task.id)
                action = "resumed_existing_task"
                task = updated
            elif source_task and source_task.status in {
                TaskStatus.PLANNED,
                TaskStatus.EXECUTING,
                TaskStatus.BLOCKED,
                TaskStatus.VERIFYING,
            }:
                action = "resumed_existing_task"
                task = source_task
            else:
                success_criteria = source_task.success_criteria if source_task and source_task.success_criteria else [payload.detail or "Reminder is handled."]
                risk_level = source_task.risk_level if source_task else RiskLevel.LOW
                task = self.task_engine.create(
                    TaskCreatePayload(
                        objective=payload.title.replace("Resume reminder: ", "", 1),
                        success_criteria=success_criteria,
                        risk_level=risk_level,
                    )
                )
                action = "created_from_reminder_context" if source_task else "created_from_reminder"
            if reminder_id:
                self.capability_bus.execute(
                    CapabilityExecutionPayload(
                        capability_name="reminders",
                        action="delete",
                        parameters={"id": reminder_id},
                    )
                )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": task.id,
                    "source_task_id": source_task_id,
                    "reminder_id": reminder_id,
                    "action": action,
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            self.task_engine.events.append(
                "task.resumed_from_reminder",
                {"task_id": task.id, "source_task_id": source_task_id, "reminder_id": reminder_id, "action": action},
            )
            self.relations.link(
                source_type="reminder",
                source_id=str(reminder_id),
                relation_type="resurfaced_task",
                target_type="task",
                target_id=task.id,
                metadata={
                    "action": action,
                    "source_task_id": source_task_id,
                    "reminder_origin": payload.metadata.get("origin"),
                },
            )
            return CandidateAcceptanceResult(action=action, task=task)

        if payload.kind in {"phase_alignment", "bootstrap"}:
            created = self.task_engine.create(
                TaskCreatePayload(
                    objective=payload.title,
                    success_criteria=[payload.detail],
                )
            )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": created.id,
                    "action": "created_task",
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            return CandidateAcceptanceResult(action="created_task", task=created)

        raise ValueError(f"Unsupported or invalid candidate acceptance: {payload.kind}")

    def auto_accept(self, payload: CandidateAutoAcceptPayload) -> CandidateAcceptanceResult:
        if not payload.auto_acceptable:
            raise ValueError("Candidate is not eligible for auto-accept.")
        if payload.needs_confirmation:
            raise ValueError("Candidate requires confirmation and cannot be auto-accepted.")
        result = self.accept(
            CandidateAcceptancePayload(
                kind=payload.kind,
                title=payload.title,
                detail=payload.detail,
                source_task_id=payload.source_task_id,
                reason_code=payload.reason_code,
                trigger_source=payload.trigger_source,
                metadata=payload.metadata,
            )
        )
        self.event_repo.append(
            "candidate.auto_accepted",
            {
                "kind": payload.kind,
                "task_id": result.task.id,
                "source_task_id": payload.source_task_id,
                "action": result.action,
                "reason_code": payload.reason_code,
                "trigger_source": payload.trigger_source,
            },
        )
        return result

    def auto_accept_eligible(self, payload: CandidateBatchAutoAcceptPayload) -> CandidateBatchAutoAcceptResult:
        accepted: list[CandidateAcceptanceResult] = []
        skipped: list[str] = []
        skip_details: list[CandidateSkipDetail] = []
        errors: list[str] = []

        for candidate in self.discover(limit=payload.limit):
            label = f"{candidate.kind}:{candidate.title}"
            if not candidate.auto_acceptable:
                skipped.append(f"{label} skipped: not auto-acceptable")
                skip_details.append(
                    CandidateSkipDetail(
                        kind=candidate.kind,
                        title=candidate.title,
                        source_task_id=candidate.source_task_id,
                        reason="not_auto_acceptable",
                        reason_code=candidate.reason_code,
                        trigger_source=candidate.trigger_source,
                    )
                )
                continue
            if candidate.needs_confirmation:
                skipped.append(f"{label} skipped: needs confirmation")
                skip_details.append(
                    CandidateSkipDetail(
                        kind=candidate.kind,
                        title=candidate.title,
                        source_task_id=candidate.source_task_id,
                        reason="needs_confirmation",
                        reason_code=candidate.reason_code,
                        trigger_source=candidate.trigger_source,
                    )
                )
                continue
            try:
                result = self.auto_accept(
                    CandidateAutoAcceptPayload(
                        kind=candidate.kind,
                        title=candidate.title,
                        detail=candidate.detail,
                        source_task_id=candidate.source_task_id,
                        reason_code=candidate.reason_code,
                        trigger_source=candidate.trigger_source,
                        metadata=candidate.metadata,
                        auto_acceptable=candidate.auto_acceptable,
                        needs_confirmation=candidate.needs_confirmation,
                    )
                )
                accepted.append(result)
            except ValueError as exc:
                errors.append(f"{label} failed: {exc}")

        skip_reason_counts = self._skip_reason_counts(skip_details)
        self.event_repo.append(
            "candidate.auto_accept_batch_completed",
            {
                "accepted_count": len(accepted),
                "skipped_count": len(skipped),
                "error_count": len(errors),
                "limit": payload.limit,
                "skip_reasons": [item.reason for item in skip_details],
                "skip_reason_counts": skip_reason_counts,
            },
        )
        return CandidateBatchAutoAcceptResult(accepted=accepted, skipped=skipped, skip_details=skip_details, errors=errors)

    @staticmethod
    def _skip_reason_counts(skip_details: list[CandidateSkipDetail]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for detail in skip_details:
            counts[detail.reason] = counts.get(detail.reason, 0) + 1
        return counts

    def defer(self, payload: CandidateDeferPayload) -> CandidateDeferResult:
        if payload.kind != "reminder_due":
            raise ValueError(f"Unsupported candidate defer: {payload.kind}")

        reminder_id = payload.metadata.get("reminder_id")
        if not reminder_id:
            raise ValueError("Reminder defer requires reminder_id metadata.")

        due_hint = payload.due_hint or str(payload.metadata.get("due_hint", "tomorrow"))
        scheduled_for = payload.scheduled_for.isoformat() if payload.scheduled_for else payload.metadata.get("scheduled_for")
        result = self.capability_bus.execute(
            CapabilityExecutionPayload(
                capability_name="reminders",
                action="reschedule",
                parameters={"id": reminder_id, "due_hint": due_hint, "scheduled_for": scheduled_for},
            )
        )
        self.event_repo.append(
            "candidate.deferred",
            {
                "kind": payload.kind,
                "task_id": payload.metadata.get("source_task_id"),
                "source_task_id": payload.metadata.get("source_task_id"),
                "reminder_id": reminder_id,
                "due_hint": due_hint,
                "scheduled_for": scheduled_for,
                "action": "rescheduled_reminder",
                "reason_code": payload.reason_code,
                "trigger_source": payload.trigger_source,
            },
        )
        return CandidateDeferResult(
            action="rescheduled_reminder",
            metadata={"reminder_id": reminder_id, "due_hint": due_hint, "scheduled_for": scheduled_for, "result": result.output},
        )

    @staticmethod
    def _is_due_reminder(reminder: dict[str, object], now: datetime) -> bool:
        scheduled_for_raw = reminder.get("scheduled_for")
        if not isinstance(scheduled_for_raw, str):
            return False
        scheduled_for = datetime.fromisoformat(scheduled_for_raw)
        if scheduled_for > now:
            return False
        last_seen_raw = reminder.get("last_seen_at")
        if not isinstance(last_seen_raw, str):
            return True
        last_seen_at = datetime.fromisoformat(last_seen_raw)
        return last_seen_at < scheduled_for


class SchedulerService:
    BASE_ESCALATION_POLICIES: dict[str, dict[TaskStatus, EscalationPolicy]] = {
        "balanced": {
            TaskStatus.BLOCKED: EscalationPolicy(
                name="blocked_risk_review",
                create_escalation_task=True,
                create_urgent_reminder=False,
                promote_risk_level=RiskLevel.HIGH,
            ),
            TaskStatus.EXECUTING: EscalationPolicy(
                name="executing_urgent_review",
                create_escalation_task=True,
                create_urgent_reminder=True,
                promote_risk_level=RiskLevel.HIGH,
                reminder_due_hint="later today",
                reminder_offset_minutes=30,
            ),
        },
        "cautious": {
            TaskStatus.BLOCKED: EscalationPolicy(
                name="cautious_blocked_urgent_review",
                create_escalation_task=True,
                create_urgent_reminder=True,
                promote_risk_level=RiskLevel.HIGH,
                reminder_due_hint="later today",
                reminder_offset_minutes=20,
            ),
            TaskStatus.EXECUTING: EscalationPolicy(
                name="cautious_executing_urgent_review",
                create_escalation_task=True,
                create_urgent_reminder=True,
                promote_risk_level=RiskLevel.HIGH,
                reminder_due_hint="later today",
                reminder_offset_minutes=15,
            ),
        },
        "bold": {
            TaskStatus.BLOCKED: EscalationPolicy(
                name="bold_blocked_review",
                create_escalation_task=True,
                create_urgent_reminder=False,
                promote_risk_level=None,
            ),
            TaskStatus.EXECUTING: EscalationPolicy(
                name="bold_executing_review",
                create_escalation_task=True,
                create_urgent_reminder=False,
                promote_risk_level=None,
            ),
        },
    }
    ESCALATION_POLICIES: dict[TaskStatus, EscalationPolicy] = {
        TaskStatus.BLOCKED: EscalationPolicy(
            name="blocked_risk_review",
            create_escalation_task=True,
            create_urgent_reminder=False,
            promote_risk_level=RiskLevel.HIGH,
        ),
        TaskStatus.EXECUTING: EscalationPolicy(
            name="executing_urgent_review",
            create_escalation_task=True,
            create_urgent_reminder=True,
            promote_risk_level=RiskLevel.HIGH,
            reminder_due_hint="later today",
            reminder_offset_minutes=30,
        ),
    }

    def __init__(
        self,
        candidate_service: CandidateTaskService,
        task_engine: TaskEngine,
        delivery: DeliveryCoordinator,
        event_repo: EventRepository,
        self_kernel: SelfKernel,
        relation_service: RelationService,
        memory_engine: MemoryEngine,
    ) -> None:
        self.candidate_service = candidate_service
        self.task_engine = task_engine
        self.delivery = delivery
        self.event_repo = event_repo
        self.self_kernel = self_kernel
        self.relation_service = relation_service
        self.memory_engine = memory_engine

    def tick(self, payload: SchedulerTickPayload) -> SchedulerTickResult:
        discovered = self.candidate_service.discover(limit=payload.candidate_limit)
        batch = self.candidate_service.auto_accept_eligible(
            CandidateBatchAutoAcceptPayload(limit=payload.candidate_limit)
        )
        stale_hit_counts = self._stalled_hit_counts()
        auto_started_task_ids = self._auto_start_planned_tasks()
        auto_verified_task_ids = self._auto_verify_executing_tasks()
        blocked_followup_task_ids = self._create_stale_blocked_followups(
            payload.stale_after_minutes, payload.escalate_after_hits, stale_hit_counts
        )
        stalled_task_ids = self._schedule_stale_executing_reminders(
            payload.stale_after_minutes, payload.escalate_after_hits, stale_hit_counts
        )
        escalations = self._create_stale_escalations(
            payload.stale_after_minutes, payload.escalate_after_hits, stale_hit_counts
        )
        escalated_task_ids = [outcome.task_id for outcome in escalations]
        result = SchedulerTickResult(
            discovered_count=len(discovered),
            auto_accepted_count=len(batch.accepted),
            auto_started_count=len(auto_started_task_ids),
            auto_verified_count=len(auto_verified_task_ids),
            blocked_followup_count=len(blocked_followup_task_ids),
            stalled_reminder_count=len(stalled_task_ids),
            escalated_count=len(escalated_task_ids),
            skipped_count=len(batch.skipped),
            error_count=len(batch.errors),
            accepted=batch.accepted,
            auto_started_task_ids=auto_started_task_ids,
            auto_verified_task_ids=auto_verified_task_ids,
            blocked_followup_task_ids=blocked_followup_task_ids,
            stalled_task_ids=stalled_task_ids,
            escalated_task_ids=escalated_task_ids,
            escalations=escalations,
            skipped=batch.skipped,
            skip_details=batch.skip_details,
            errors=batch.errors,
        )
        self.event_repo.append(
            "scheduler.tick.completed",
            {
                "candidate_limit": payload.candidate_limit,
                "discovered_count": result.discovered_count,
                "auto_accepted_count": result.auto_accepted_count,
                "auto_started_count": result.auto_started_count,
                "auto_verified_count": result.auto_verified_count,
                "blocked_followup_count": result.blocked_followup_count,
                "stalled_reminder_count": result.stalled_reminder_count,
                "escalated_count": result.escalated_count,
                "skipped_count": result.skipped_count,
                "skip_reason_counts": CandidateTaskService._skip_reason_counts(result.skip_details),
                "error_count": result.error_count,
            },
        )
        return result

    def _auto_start_planned_tasks(self) -> list[str]:
        started: list[str] = []
        for task in self.task_engine.list():
            if task.status != TaskStatus.PLANNED:
                continue
            if task.execution_plan.confirmation_required:
                continue
            self.delivery.execute_task(task.id)
            started.append(task.id)
        return started

    def _auto_verify_executing_tasks(self) -> list[str]:
        verified: list[str] = []
        for task in self.task_engine.list():
            if task.status != TaskStatus.EXECUTING:
                continue
            if task.execution_plan.confirmation_required:
                continue
            self.delivery.verify_task(task.id, TaskVerificationPayload())
            verified.append(task.id)
        return verified

    def _create_stale_blocked_followups(
        self, stale_after_minutes: int, escalate_after_hits: int, stale_hit_counts: dict[str, int]
    ) -> list[str]:
        now = utc_now()
        stale_cutoff = now - timedelta(minutes=stale_after_minutes)
        existing_followups = {
            task.objective
            for task in self.task_engine.list()
            if task.objective.startswith("Resolve blocker:")
        }
        created: list[str] = []
        for task in self.task_engine.list():
            if task.status != TaskStatus.BLOCKED:
                continue
            if task.updated_at > stale_cutoff:
                continue
            if self._should_escalate(task.id, escalate_after_hits, stale_hit_counts):
                continue
            followup_objective = f"Resolve blocker: {task.objective}"
            if followup_objective in existing_followups:
                continue
            followup = self.task_engine.create(
                TaskCreatePayload(
                    objective=followup_objective,
                    success_criteria=["Blocker is clarified or removed."],
                    risk_level=task.risk_level,
                )
            )
            created.append(task.id)
            self.event_repo.append(
                "scheduler.stalled_task.followup_created",
                {"task_id": task.id, "followup_task_id": followup.id, "stale_after_minutes": stale_after_minutes},
            )
        return created

    def _schedule_stale_executing_reminders(
        self, stale_after_minutes: int, escalate_after_hits: int, stale_hit_counts: dict[str, int]
    ) -> list[str]:
        now = utc_now()
        stale_cutoff = now - timedelta(minutes=stale_after_minutes)
        reminders = json.loads(
            self.candidate_service.capability_bus.execute(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        existing_source_ids = {
            reminder.get("source_task_id")
            for reminder in reminders
            if reminder.get("source_task_id")
        }

        reminded: list[str] = []
        for task in self.task_engine.list():
            if task.status != TaskStatus.EXECUTING:
                continue
            if task.updated_at > stale_cutoff:
                continue
            if self._should_escalate(task.id, escalate_after_hits, stale_hit_counts):
                continue
            if task.id in existing_source_ids:
                continue
            self.candidate_service.capability_bus.execute(
                CapabilityExecutionPayload(
                    capability_name="reminders",
                    action="create",
                    parameters={
                        "title": f"Follow up stalled task: {task.objective}",
                        "note": f"Task {task.id} has been {task.status.value} since {task.updated_at.isoformat()}",
                        "due_hint": "tomorrow",
                        "scheduled_for": (now + timedelta(days=1)).isoformat(),
                        "source_task_id": task.id,
                        "origin": "scheduler_tick",
                    },
                )
            )
            reminded.append(task.id)
            self.event_repo.append(
                "scheduler.stalled_task.reminder_created",
                {"task_id": task.id, "status": task.status.value, "stale_after_minutes": stale_after_minutes},
            )
        return reminded

    def _create_stale_escalations(
        self, stale_after_minutes: int, escalate_after_hits: int, stale_hit_counts: dict[str, int]
    ) -> list[EscalationOutcome]:
        now = utc_now()
        stale_cutoff = now - timedelta(minutes=stale_after_minutes)
        active_policies = self._escalation_policies()
        existing_escalations = {
            task.objective
            for task in self.task_engine.list()
            if task.objective.startswith("Escalate stalled task:")
        }
        existing_reminders = json.loads(
            self.candidate_service.capability_bus.execute(
                CapabilityExecutionPayload(capability_name="reminders", action="list", parameters={})
            ).output
        )
        reminders_by_source_id = {
            reminder.get("source_task_id"): reminder
            for reminder in existing_reminders
            if reminder.get("source_task_id")
        }
        escalated: list[EscalationOutcome] = []
        for task in self.task_engine.list():
            if task.status not in {TaskStatus.BLOCKED, TaskStatus.EXECUTING}:
                continue
            if task.updated_at > stale_cutoff:
                continue
            if not self._should_escalate(task.id, escalate_after_hits, stale_hit_counts):
                continue
            policy = self._policy_for_task(task, active_policies)
            if not policy:
                continue
            escalation_objective = f"Escalate stalled task: {task.objective}"
            escalation_task_id: str | None = None
            reminder_id: str | None = None
            risk_promoted = False
            actions: list[str] = []
            if policy.promote_risk_level and task.risk_level != policy.promote_risk_level:
                task.risk_level = policy.promote_risk_level
                task.updated_at = now
                self.task_engine.repo.update(task)
                risk_promoted = True
                actions.append(f"promote_risk:{policy.promote_risk_level.value}")
            if task.execution_plan.confirmation_required:
                actions.append("confirmation_guardrail")
            if policy.create_escalation_task and escalation_objective not in existing_escalations:
                escalation = self.task_engine.create(
                    TaskCreatePayload(
                        objective=escalation_objective,
                        success_criteria=["Escalation path is reviewed and a decision is made."],
                        risk_level=task.risk_level,
                    )
                )
                escalation_task_id = escalation.id
                existing_escalations.add(escalation_objective)
                actions.append("create_escalation_task")
            if policy.create_urgent_reminder:
                existing_reminder = reminders_by_source_id.get(task.id)
                if existing_reminder:
                    self.candidate_service.capability_bus.execute(
                        CapabilityExecutionPayload(
                            capability_name="reminders",
                            action="reschedule",
                            parameters={
                                "id": existing_reminder["id"],
                                "due_hint": policy.reminder_due_hint,
                                "scheduled_for": (now + timedelta(minutes=policy.reminder_offset_minutes)).isoformat(),
                                "origin": "scheduler_escalation",
                            },
                        )
                    )
                    reminder_id = str(existing_reminder["id"])
                    actions.append("reschedule_urgent_reminder")
                else:
                    reminder_result = self.candidate_service.capability_bus.execute(
                        CapabilityExecutionPayload(
                            capability_name="reminders",
                            action="create",
                            parameters={
                                "title": f"Escalated review needed: {task.objective}",
                                "note": f"Escalation triggered for task {task.id} in status {task.status.value}",
                                "due_hint": policy.reminder_due_hint,
                                "scheduled_for": (now + timedelta(minutes=policy.reminder_offset_minutes)).isoformat(),
                                "source_task_id": task.id,
                                "origin": "scheduler_escalation",
                            },
                        )
                    )
                    reminder = ReminderRecord.model_validate_json(reminder_result.output)
                    reminder_id = reminder.id
                    reminders_by_source_id[task.id] = reminder.model_dump(mode="json")
                    actions.append("create_urgent_reminder")
            if not actions:
                continue
            outcome = EscalationOutcome(
                task_id=task.id,
                status=task.status,
                policy_name=policy.name,
                actions=actions,
                escalation_task_id=escalation_task_id,
                reminder_id=reminder_id,
                risk_promoted=risk_promoted,
            )
            escalated.append(outcome)
            self.event_repo.append(
                "scheduler.stalled_task.escalated",
                {
                    "task_id": task.id,
                    "escalation_task_id": escalation_task_id,
                    "reminder_id": reminder_id,
                    "status": task.status.value,
                    "policy_name": policy.name,
                    "actions": actions,
                    "risk_promoted": risk_promoted,
                    "stale_after_minutes": stale_after_minutes,
                    "escalate_after_hits": escalate_after_hits,
                },
            )
        return escalated

    def _stalled_hit_counts(self) -> dict[str, int]:
        hit_counts: dict[str, int] = {}
        for task in self.task_engine.list():
            historical_events = self.event_repo.list_for_task(task.id, limit=200)
            hit_counts[task.id] = sum(
                1
                for event in historical_events
                if event.event_type in {"scheduler.stalled_task.followup_created", "scheduler.stalled_task.reminder_created"}
            )
        return hit_counts

    @staticmethod
    def _should_escalate(task_id: str, escalate_after_hits: int, stale_hit_counts: dict[str, int]) -> bool:
        prior_hits = stale_hit_counts.get(task_id, 0)
        return prior_hits + 1 >= escalate_after_hits

    def _escalation_policies(self) -> dict[TaskStatus, EscalationPolicy]:
        risk_style = self.self_kernel.get().risk_style.strip().lower()
        return self.BASE_ESCALATION_POLICIES.get(risk_style, self.ESCALATION_POLICIES)

    def _policy_for_task(
        self, task: TaskRecord, active_policies: dict[TaskStatus, EscalationPolicy]
    ) -> EscalationPolicy | None:
        style_override = next((tag.split(":", 1)[1] for tag in task.tags if tag.startswith("governance:")), None)
        resurfaced_origins = self._resurfaced_reminder_origins(task.id)
        relationship_style = self._relationship_context_style(task)
        reflection_style = self._reflection_context_style(task)
        if style_override:
            policy = self.BASE_ESCALATION_POLICIES.get(style_override, active_policies).get(task.status)
        elif reflection_style:
            policy = self.BASE_ESCALATION_POLICIES.get(reflection_style, active_policies).get(task.status)
        elif relationship_style:
            policy = self.BASE_ESCALATION_POLICIES.get(relationship_style, active_policies).get(task.status)
        elif any(origin in {"scheduler_tick", "scheduler_escalation"} for origin in resurfaced_origins):
            policy = self.BASE_ESCALATION_POLICIES["cautious"].get(task.status)
        else:
            policy = active_policies.get(task.status)
        if not policy:
            return None

        updated = policy.model_copy(deep=True)
        if "escalation:urgent_reminder" in task.tags:
            updated.create_urgent_reminder = True
        if "escalation:no_urgent_reminder" in task.tags:
            updated.create_urgent_reminder = False
        if "escalation:no_risk_promotion" in task.tags:
            updated.promote_risk_level = None
        if "escalation:promote_high" in task.tags:
            updated.promote_risk_level = RiskLevel.HIGH
        if task.execution_plan.confirmation_required:
            updated.create_urgent_reminder = True
        return updated

    def _resurfaced_reminder_origins(self, task_id: str) -> set[str]:
        relations = self.relation_service.list_for_entity("task", task_id, limit=50)
        return {
            str(relation.metadata.get("reminder_origin"))
            for relation in relations
            if relation.relation_type == "resurfaced_task" and relation.metadata.get("reminder_origin")
        }

    def _relationship_context_style(self, task: TaskRecord) -> str | None:
        objective = task.objective.lower()
        profile = self.self_kernel.get()
        for entry in profile.relationship_network:
            if ":" not in entry:
                continue
            raw_style, raw_name = entry.split(":", 1)
            style = raw_style.strip().lower()
            name = raw_name.strip().lower()
            if not name or name not in objective:
                continue
            if style in {"high_risk", "protected", "cautious"}:
                return "cautious"
            if style in {"balanced", "bold"}:
                return style
        return None

    def _reflection_context_style(self, task: TaskRecord) -> str | None:
        objective = task.objective.lower()
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
                if not keyword or keyword not in objective:
                    continue
                if style in {"high_risk", "protected", "cautious"}:
                    return "cautious"
                if style in {"balanced", "bold"}:
                    return style
        return None
