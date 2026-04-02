from __future__ import annotations

from datetime import datetime, timedelta
import re

from ai_os.capabilities import CapabilityRegistry
from ai_os.domain import (
    CalendarEventRecord,
    CapabilityExecutionPayload,
    CapabilityExecutionResult,
    ExecutionMode,
    InputPayload,
    IntakeResponse,
    MemoryCreatePayload,
    MemoryLayer,
    MemoryRecord,
    MemoryType,
    ReminderRecord,
    SelfProfile,
    TaskConfirmationPayload,
    TaskReflectionPayload,
    TaskRecord,
    TaskStatus,
    TaskVerificationPayload,
    utc_now,
)
from ai_os.kernel import (
    CognitionEngine,
    ExecutionRunService,
    GoalService,
    IntentEngine,
    MemoryEngine,
    RelationService,
    SelfKernel,
    TaskEngine,
)
from ai_os.runtimes import RuntimeRegistry
from ai_os.policy import PolicyDecision, PolicyEngine


class IntakeCoordinator:
    def __init__(
        self,
        self_kernel: SelfKernel,
        goal_service: GoalService | None,
        intent_engine: IntentEngine,
        cognition_engine: CognitionEngine,
        task_engine: TaskEngine,
    ) -> None:
        self.self_kernel = self_kernel
        self.goal_service = goal_service
        self.intent_engine = intent_engine
        self.cognition_engine = cognition_engine
        self.task_engine = task_engine

    def process(self, payload: InputPayload) -> IntakeResponse:
        profile = self.self_kernel.get()
        intent = self.intent_engine.evaluate(payload, profile)
        cognition = self.cognition_engine.analyze(intent, profile)
        task = self.task_engine.ensure_from_intent(intent, cognition)
        if task:
            goal_ids = self._infer_goal_links(intent.goal, profile)
            if goal_ids:
                task.linked_goal_ids = goal_ids
                task.updated_at = utc_now()
                task = self.task_engine.repo.update(task)
        return IntakeResponse(intent=intent, cognition=cognition, task=task)

    def _infer_goal_links(self, goal_text: str, profile: SelfProfile) -> list[str]:
        goal_text_lower = goal_text.lower()
        matched_ids = [
            goal.id for goal in (self.goal_service.active() if self.goal_service else []) if goal.title.lower() in goal_text_lower
        ]
        if matched_ids:
            return matched_ids
        return [goal for goal in profile.long_term_goals if goal and goal.lower() in goal_text_lower]


class DeliveryCoordinator:
    def __init__(
        self,
        task_engine: TaskEngine,
        memory_engine: MemoryEngine,
        capability_bus: CapabilityRegistry,
        relation_service: RelationService,
        execution_run_service: ExecutionRunService,
        runtime_registry: RuntimeRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.task_engine = task_engine
        self.memory_engine = memory_engine
        self.capability_bus = capability_bus
        self.relations = relation_service
        self.execution_runs = execution_run_service
        self.runtime_registry = runtime_registry
        self.policy_engine = policy_engine or PolicyEngine()

    def execute_capability(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        return self.capability_bus.execute(payload)

    def execute_task(self, task_id: str) -> TaskRecord:
        task = self.task_engine.mark_executing(task_id)
        run_metadata: dict[str, object] = {"execution_mode": task.execution_mode.value}
        if task.runtime_name:
            run_metadata["runtime_name"] = task.runtime_name
        elif task.execution_plan.runtime_name:
            run_metadata["runtime_name"] = task.execution_plan.runtime_name
        run = self.execution_runs.start(task.id, metadata=run_metadata)
        policy_decision = self.policy_engine.before_execute(task)
        self._record_policy_decision(task, run.id, policy_decision)
        if not policy_decision.allowed:
            return self._block_task_via_policy(task, run.id, policy_decision)
        executor_name = task.execution_plan.mode.value
        produced_output = False
        if task.execution_plan.mode == ExecutionMode.MEMORY_CAPTURE:
            produced_output = self._execute_memory_capture(task, run.id)
        elif task.execution_plan.mode == ExecutionMode.CALENDAR_EVENT:
            produced_output = self._execute_calendar_event(task, run.id)
        elif task.execution_plan.mode == ExecutionMode.REMINDER:
            produced_output = self._execute_reminder(task, run.id)
        elif task.execution_plan.mode == ExecutionMode.MESSAGE_DRAFT:
            produced_output = self._execute_message_draft(task, run.id)
        else:
            produced_output = self._execute_file_artifact(task, run.id)

        task.updated_at = utc_now()
        if produced_output:
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
        if task.status != TaskStatus.BLOCKED:
            raise ValueError(f"Cannot confirm task from {task.status.value}.")

        is_message_confirmation = task.execution_plan.mode == ExecutionMode.MESSAGE_DRAFT
        is_policy_confirmation = task.blocker_reason == "Awaiting policy confirmation before external side effect."
        if not is_message_confirmation and not is_policy_confirmation:
            raise ValueError("Task confirmation is only supported for message draft or policy-gated tasks.")

        note = payload.note or (
            "User approved message delivery."
            if is_message_confirmation and payload.approved
            else "User approved policy-gated execution."
            if payload.approved
            else "User rejected task execution."
        )
        task.verification_notes.append(note)
        if payload.approved:
            if is_message_confirmation:
                task.status = TaskStatus.EXECUTING
            else:
                if PolicyEngine.POLICY_OVERRIDE_TAG not in task.tags:
                    task.tags.append(PolicyEngine.POLICY_OVERRIDE_TAG)
                task.status = TaskStatus.PLANNED
            task.blocker_reason = None
            self.task_engine.events.append("task.confirmed", {"task_id": task.id, "approved": True, "note": note})
        else:
            task.status = TaskStatus.ARCHIVED
            task.blocker_reason = "User rejected message delivery."
            self.task_engine.events.append("task.confirmed", {"task_id": task.id, "approved": False, "note": note})
        task.updated_at = utc_now()
        saved = self.task_engine.repo.update(task)
        return saved

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
            f"- Linked Goals: {', '.join(task.linked_goal_ids) if task.linked_goal_ids else 'None'}",
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
        return self._execute_file_artifact_impl(task, run_id)

    def _execute_file_artifact_impl(self, task: TaskRecord, run_id: str) -> bool:
        runtime_name = self._select_runtime(task)
        runtime_execution: dict[str, str] | None = None
        if runtime_name and self.runtime_registry:
            preview = self.runtime_registry.prepare_task(runtime_name, task)
            invocation = self.runtime_registry.build_invocation(runtime_name, task)
            task.verification_notes.append(f"Runtime prepared: {runtime_name}")
            self.execution_runs.annotate(
                run_id,
                {
                    "runtime_name": runtime_name,
                    "runtime_status": preview["status"],
                    "runtime_invocation": invocation.model_dump(mode="json"),
                },
            )
            self.relations.link(
                source_type="execution_run",
                source_id=run_id,
                relation_type="prepared_runtime",
                target_type="runtime",
                target_id=runtime_name,
                metadata=preview,
            )
            runtime_execution = self.runtime_registry.execute_task(runtime_name, task)
            task.verification_notes.append(f"Runtime executed: {runtime_name}")
            self.execution_runs.annotate(
                run_id,
                {
                    "runtime_summary": runtime_execution.get("summary", ""),
                    "runtime_command_preview": runtime_execution.get("command_preview", ""),
                    "runtime_execution_status": runtime_execution.get("execution_status", ""),
                    "runtime_exit_code": runtime_execution.get("exit_code"),
                    "runtime_live_execution": runtime_execution.get("live_execution", False),
                    "runtime_stdout": runtime_execution.get("stdout", ""),
                    "runtime_stderr": runtime_execution.get("stderr", ""),
                    "runtime_executed_command": runtime_execution.get("executed_command", ""),
                },
            )
            self.relations.link(
                source_type="execution_run",
                source_id=run_id,
                relation_type="executed_runtime",
                target_type="runtime",
                target_id=runtime_name,
                metadata=runtime_execution,
            )
        artifact_path = self._artifact_path_for(task)
        plan_content = (
            runtime_execution["artifact_content"]
            if runtime_execution and runtime_execution.get("artifact_content")
            else self._render_task_artifact(task)
        )
        self.execute_capability(
            CapabilityExecutionPayload(
                capability_name="local_files",
                action="write_text",
                parameters={"path": artifact_path, "content": plan_content},
            )
        )
        self.execution_runs.annotate(
            run_id,
            {
                "artifact_path": artifact_path,
                "artifact_kind": "file_artifact",
            },
        )
        task.artifact_paths = sorted({*task.artifact_paths, artifact_path})
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="produced_artifact",
            target_type="artifact",
            target_id=artifact_path,
            metadata={"path": artifact_path, **({"runtime": runtime_name} if runtime_name else {})},
        )
        self.relations.link(
            "execution_run",
            run_id,
            "produced_artifact",
            "artifact",
            artifact_path,
            metadata={"path": artifact_path, **({"runtime": runtime_name} if runtime_name else {})},
        )
        return True

    @staticmethod
    def _select_runtime(task: TaskRecord) -> str | None:
        if task.runtime_name:
            return task.runtime_name
        if task.execution_plan.runtime_name:
            return task.execution_plan.runtime_name
        lowered = " ".join([task.objective, " ".join(task.tags)]).lower()
        coding_tokens = ("code", "repo", "git", "refactor", "implement", "feature", "bug", "runtime", "api")
        return "claude-code" if any(token in lowered for token in coding_tokens) else None

    def _execute_memory_capture(self, task: TaskRecord, run_id: str) -> bool:
        record = self.memory_engine.create(
            MemoryCreatePayload(
                memory_type=MemoryType.KNOWLEDGE,
                layer=MemoryLayer.SEMANTIC,
                title=task.objective,
                content=f"Captured from task {task.id}: {task.objective}",
                tags=["task_capture", task.id],
                source="task_execution",
                confidence=0.85,
                freshness="active",
                related_goal_ids=task.linked_goal_ids,
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
        return True

    def _execute_message_draft(self, task: TaskRecord, run_id: str) -> bool:
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
        return True

    def _execute_reminder(self, task: TaskRecord, run_id: str) -> bool:
        if not self._allow_external_side_effect(task, run_id, "reminder.create"):
            return False
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
        return True

    def _execute_calendar_event(self, task: TaskRecord, run_id: str) -> bool:
        if not self._allow_external_side_effect(task, run_id, "calendar.create"):
            return False
        scheduled_for, due_hint = self._calendar_schedule_for(task)
        result = self.execute_capability(
            CapabilityExecutionPayload(
                capability_name="calendar",
                action="create",
                parameters={
                    "title": task.objective,
                    "note": f"Scheduled from task {task.id}",
                    "due_hint": due_hint,
                    "scheduled_for": scheduled_for.isoformat(),
                    "duration_minutes": 45,
                    "source_task_id": task.id,
                },
            )
        )
        event = CalendarEventRecord.model_validate_json(result.output)
        task.verification_notes.append(f"Calendar event scheduled: {event.id}")
        self.relations.link(
            source_type="task",
            source_id=task.id,
            relation_type="scheduled_calendar_event",
            target_type="calendar_event",
            target_id=event.id,
        )
        self.relations.link("execution_run", run_id, "scheduled_calendar_event", "calendar_event", event.id)
        return True

    @staticmethod
    def _calendar_schedule_for(task: TaskRecord) -> tuple[datetime, str]:
        objective = task.objective.strip()
        now = utc_now()
        lowered = objective.lower()

        if "tomorrow" in lowered or "明天" in objective:
            day_offset = 1
            due_hint = "tomorrow"
        elif "next week" in lowered or "下周" in objective:
            day_offset = 7
            due_hint = "next week"
        else:
            day_offset = 0
            due_hint = "later today"

        base = now + timedelta(days=day_offset)
        hour = 13
        minute = 0

        match = re.search(r"(上午|中午|下午|晚上)?\s*(\d{1,2})\s*点(?:(\d{1,2})分?)?", objective)
        if match:
            period = match.group(1) or ""
            parsed_hour = int(match.group(2))
            parsed_minute = int(match.group(3) or "0")
            if period in {"下午", "晚上"} and parsed_hour < 12:
                parsed_hour += 12
            elif period == "中午" and parsed_hour < 11:
                parsed_hour += 12
            hour = min(parsed_hour, 23)
            minute = min(parsed_minute, 59)
        elif "morning" in lowered or "上午" in objective:
            hour = 9
        elif "afternoon" in lowered or "下午" in objective:
            hour = 14
        elif "evening" in lowered or "晚上" in objective:
            hour = 19

        scheduled_for = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_for <= now:
            scheduled_for = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            due_hint = "later today"
        return scheduled_for, due_hint

    def _allow_external_side_effect(self, task: TaskRecord, run_id: str, effect_type: str) -> bool:
        decision = self.policy_engine.before_external_side_effect(task, effect_type)
        self._record_policy_decision(task, run_id, decision)
        if decision.allowed:
            return True
        self._block_task_via_policy(task, run_id, decision)
        return False

    def _record_policy_decision(self, task: TaskRecord, run_id: str, decision: PolicyDecision) -> None:
        metadata = {"hook": decision.hook, "allowed": decision.allowed, **decision.metadata}
        self.execution_runs.annotate(run_id, {f"policy_{decision.hook}": metadata})
        self.relations.link(
            "execution_run",
            run_id,
            "policy_evaluated",
            "task",
            task.id,
            metadata=metadata,
        )
        if decision.notes:
            task.verification_notes.extend([f"Policy {decision.hook}: {note}" for note in decision.notes])

    def _block_task_via_policy(self, task: TaskRecord, run_id: str, decision: PolicyDecision) -> TaskRecord:
        task.status = TaskStatus.BLOCKED
        task.blocker_reason = decision.reason or "Blocked by policy."
        task.updated_at = utc_now()
        if decision.reason:
            task.verification_notes.append(f"Policy blocked execution: {decision.reason}")
        self.task_engine.events.append(
            "task.blocked_by_policy",
            {
                "task_id": task.id,
                "execution_run_id": run_id,
                "hook": decision.hook,
                "reason": task.blocker_reason,
                "metadata": decision.metadata,
            },
        )
        self.execution_runs.complete(
            run_id,
            TaskStatus.BLOCKED.value,
            metadata={"policy_block_reason": task.blocker_reason, "policy_hook": decision.hook},
        )
        return self.task_engine.repo.update(task)

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
            elif normalized == "calendar event scheduled":
                evidence_notes.append(self._calendar_evidence(task))
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

    @staticmethod
    def _calendar_evidence(task: TaskRecord) -> str:
        if any(note.lower().startswith("calendar event scheduled:") for note in task.verification_notes):
            return "Calendar event scheduled"
        return "Missing calendar event scheduled evidence"
