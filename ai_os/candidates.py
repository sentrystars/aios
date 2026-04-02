from __future__ import annotations

from datetime import datetime, timedelta
import json

from ai_os.capabilities import CapabilityBus
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
    EscalationOutcome,
    EscalationPolicy,
    EventRecord,
    MemoryType,
    ReminderRecord,
    RiskLevel,
    SchedulerTickPayload,
    SchedulerTickResult,
    TaskCreatePayload,
    TaskRecord,
    TaskStatus,
    TaskVerificationPayload,
    TimelineItem,
    utc_now,
)
from ai_os.kernel import GoalService, MemoryEngine, RelationService, SelfKernel, TaskEngine
from ai_os.runtimes import RuntimeRegistry
from ai_os.storage import EventRepository
from ai_os.workflows import DeliveryCoordinator

class CandidateTaskService:
    POLICY_MAP: dict[str, dict[str, object]] = {
        "blocked_task": {"priority": 5, "auto_acceptable": False, "needs_confirmation": True},
        "executing_follow_up": {"priority": 4, "auto_acceptable": True, "needs_confirmation": False},
        "captured_task": {"priority": 3, "auto_acceptable": True, "needs_confirmation": False},
        "goal_review": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "needs_confirmation_gate": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "governance_review": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "empty_phase": {"priority": 2, "auto_acceptable": False, "needs_confirmation": False},
        "phase_change": {"priority": 4, "auto_acceptable": False, "needs_confirmation": False},
        "due_reminder": {"priority": 4, "auto_acceptable": True, "needs_confirmation": False},
        "due_calendar_event": {"priority": 4, "auto_acceptable": True, "needs_confirmation": False},
    }

    def __init__(
        self,
        self_kernel: SelfKernel,
        goal_service: GoalService | None,
        task_engine: TaskEngine,
        event_repo: EventRepository,
        capability_bus: CapabilityBus,
        relation_service: RelationService,
        runtime_registry: RuntimeRegistry | None = None,
    ) -> None:
        self.self_kernel = self_kernel
        self.goal_service = goal_service
        self.task_engine = task_engine
        self.event_repo = event_repo
        self.capability_bus = capability_bus
        self.runtime_registry = runtime_registry
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

        if self.goal_service:
            active_goals = self.goal_service.active()
            linked_goal_ids = {goal_id for task in tasks for goal_id in task.linked_goal_ids}
            for goal in active_goals:
                if goal.id in linked_goal_ids:
                    continue
                policy = self._policy_for("goal_review")
                candidates.append(
                    CandidateTask(
                        kind="goal_review",
                        title=f"Create execution path for goal: {goal.title}",
                        detail="Active goal has no linked task yet.",
                        reason_code="goal_review",
                        trigger_source="goal_graph",
                        metadata={"goal_id": goal.id, "goal_title": goal.title},
                        priority=policy["priority"],
                        auto_acceptable=policy["auto_acceptable"],
                        needs_confirmation=policy["needs_confirmation"],
                    )
                )

        reminders = json.loads(
            self.capability_bus.execute(
                CapabilityExecutionPayload(capability_name="aios_local_reminders", action="list", parameters={})
            ).output
        )
        due_reminders: list[dict] = []
        for reminder in reminders:
            if not self._is_due_scheduled_item(reminder, now):
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
                        capability_name="aios_local_reminders",
                        action="mark_seen",
                        parameters={"id": reminder["id"], "seen_at": now.isoformat()},
                    )
                )

        calendar_events = json.loads(
            self.capability_bus.execute(
                CapabilityExecutionPayload(capability_name="aios_local_calendar", action="list", parameters={})
            ).output
        )
        due_calendar_events: list[dict] = []
        for event in calendar_events:
            if not self._is_due_scheduled_item(event, now):
                continue
            due_calendar_events.append(event)
            source_task = self.task_engine.repo.get(event.get("source_task_id")) if event.get("source_task_id") else None
            policy = self._policy_for_task_candidate(source_task, "due_calendar_event")
            candidates.append(
                CandidateTask(
                    kind="calendar_due",
                    title=f"Resume calendar event: {event.get('title', 'Untitled event')}",
                    detail=event.get("note", "Calendar event is due for follow-up."),
                    source_task_id=event.get("source_task_id"),
                    reason_code="due_calendar_event",
                    trigger_source="calendar_schedule",
                    metadata={
                        "calendar_event_id": event.get("id"),
                        "due_hint": event.get("due_hint", "unspecified"),
                        "scheduled_for": event.get("scheduled_for"),
                        "source_task_id": event.get("source_task_id"),
                        "origin": event.get("origin"),
                    },
                    priority=policy["priority"],
                    auto_acceptable=policy["auto_acceptable"],
                    needs_confirmation=policy["needs_confirmation"],
                )
            )

        for event in due_calendar_events:
            if event.get("id"):
                self.capability_bus.execute(
                    CapabilityExecutionPayload(
                        capability_name="aios_local_calendar",
                        action="mark_seen",
                        parameters={"id": event["id"], "seen_at": now.isoformat()},
                    )
                )

        candidates.sort(key=lambda item: item.priority, reverse=True)
        return candidates[:limit]

    def list(self, limit: int = 10) -> list[CandidateTask]:
        return self.discover(limit=limit)

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
        elif bold and reason_code in {"captured_task", "due_reminder", "due_calendar_event"}:
            policy["auto_acceptable"] = True
            policy["needs_confirmation"] = False
        if task.execution_plan.confirmation_required:
            policy["auto_acceptable"] = False
            policy["needs_confirmation"] = True
            policy["priority"] = max(int(policy["priority"]), 4)
        if reason_code in {"captured_task", "due_reminder", "due_calendar_event"}:
            autonomy_score = cls._task_autonomy_score(task)
            if autonomy_score >= 3:
                policy["priority"] = 5
                policy["auto_acceptable"] = True
                policy["needs_confirmation"] = False
            elif autonomy_score >= 2:
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

    @staticmethod
    def _task_autonomy_score(task: TaskRecord) -> int:
        score = 0
        tags = set(task.tags)
        if task.implementation_contract is not None:
            score += 2
        if task.execution_mode.value == "file_artifact":
            score += 1
        if task.runtime_name or task.execution_plan.runtime_name:
            score += 1
        if task.intelligence_trace.get("provider"):
            score += 1
        if "intelligence:cloud" in tags or "intelligence:deepseek" in tags:
            score += 1
        if "task:implementation" in tags:
            score += 1
        if task.execution_plan.confirmation_required:
            score -= 3
        if "governance:cautious" in tags or "guardrail:reflection" in tags:
            score -= 2
        return max(score, 0)

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

        if payload.kind in {"reminder_due", "calendar_due"}:
            reminder_id = payload.metadata.get("reminder_id")
            calendar_event_id = payload.metadata.get("calendar_event_id")
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
                        capability_name="aios_local_reminders",
                        action="delete",
                        parameters={"id": reminder_id},
                    )
                )
            if calendar_event_id:
                self.capability_bus.execute(
                    CapabilityExecutionPayload(
                        capability_name="aios_local_calendar",
                        action="delete",
                        parameters={"id": calendar_event_id},
                    )
                )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": task.id,
                    "source_task_id": source_task_id,
                    "reminder_id": reminder_id,
                    "calendar_event_id": calendar_event_id,
                    "action": action,
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            self.task_engine.events.append(
                "task.resumed_from_reminder",
                {
                    "task_id": task.id,
                    "source_task_id": source_task_id,
                    "reminder_id": reminder_id,
                    "calendar_event_id": calendar_event_id,
                    "action": action,
                },
            )
            self.relations.link(
                source_type="calendar_event" if calendar_event_id else "reminder",
                source_id=str(calendar_event_id or reminder_id),
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

        if payload.kind == "goal_review":
            goal_id = payload.metadata.get("goal_id")
            goal_title = str(payload.metadata.get("goal_title", payload.title))
            created = self.task_engine.create(
                TaskCreatePayload(
                    objective=f"Advance goal: {goal_title}",
                    success_criteria=["A concrete execution path exists for this goal."],
                    linked_goal_ids=[str(goal_id)] if goal_id else [],
                )
            )
            self.event_repo.append(
                "candidate.accepted",
                {
                    "kind": payload.kind,
                    "task_id": created.id,
                    "goal_id": goal_id,
                    "action": "created_goal_task",
                    "reason_code": payload.reason_code,
                    "trigger_source": payload.trigger_source,
                },
            )
            return CandidateAcceptanceResult(action="created_goal_task", task=created)

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
        if payload.kind not in {"reminder_due", "calendar_due"}:
            raise ValueError(f"Unsupported candidate defer: {payload.kind}")

        reminder_id = payload.metadata.get("reminder_id")
        calendar_event_id = payload.metadata.get("calendar_event_id")
        if not reminder_id and not calendar_event_id:
            raise ValueError("Candidate defer requires reminder_id or calendar_event_id metadata.")

        due_hint = payload.due_hint or str(payload.metadata.get("due_hint", "tomorrow"))
        scheduled_for = payload.scheduled_for.isoformat() if payload.scheduled_for else payload.metadata.get("scheduled_for")
        capability_name = "aios_local_calendar" if calendar_event_id else "aios_local_reminders"
        entity_id = calendar_event_id or reminder_id
        result = self.capability_bus.execute(
            CapabilityExecutionPayload(
                capability_name=capability_name,
                action="reschedule",
                parameters={"id": entity_id, "due_hint": due_hint, "scheduled_for": scheduled_for},
            )
        )
        self.event_repo.append(
            "candidate.deferred",
            {
                "kind": payload.kind,
                "task_id": payload.metadata.get("source_task_id"),
                "source_task_id": payload.metadata.get("source_task_id"),
                "reminder_id": reminder_id,
                "calendar_event_id": calendar_event_id,
                "due_hint": due_hint,
                "scheduled_for": scheduled_for,
                "action": "rescheduled_calendar_event" if calendar_event_id else "rescheduled_reminder",
                "reason_code": payload.reason_code,
                "trigger_source": payload.trigger_source,
            },
        )
        return CandidateDeferResult(
            action="rescheduled_calendar_event" if calendar_event_id else "rescheduled_reminder",
            metadata={
                "reminder_id": reminder_id,
                "calendar_event_id": calendar_event_id,
                "due_hint": due_hint,
                "scheduled_for": scheduled_for,
                "result": result.output,
            },
        )

    @staticmethod
    def _is_due_scheduled_item(reminder: dict[str, object], now: datetime) -> bool:
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
