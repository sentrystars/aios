from __future__ import annotations

from datetime import datetime, timedelta
import json

from ai_os.capabilities import CapabilityBus
from ai_os.candidates import CandidateTaskService
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
from ai_os.storage import EventRepository
from ai_os.workflows import DeliveryCoordinator

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
        goal_service: GoalService | None = None,
    ) -> None:
        self.candidate_service = candidate_service
        self.task_engine = task_engine
        self.delivery = delivery
        self.event_repo = event_repo
        self.self_kernel = self_kernel
        self.relation_service = relation_service
        self.memory_engine = memory_engine
        self.goal_service = goal_service

    def tick(self, payload: SchedulerTickPayload) -> SchedulerTickResult:
        if self.goal_service:
            self.goal_service.refresh_progress(self.task_engine.list())
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
        if self.goal_service:
            self.goal_service.refresh_progress(self.task_engine.list())
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
        planned_tasks = [task for task in self.task_engine.list() if task.status == TaskStatus.PLANNED]
        planned_tasks.sort(
            key=lambda task: (self._planned_task_autonomy_score(task), task.updated_at),
            reverse=True,
        )
        for task in planned_tasks:
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
            if task.objective.startswith("Resolve blocker:") or task.objective.startswith("Replan task:")
        }
        created: list[str] = []
        for task in self.task_engine.list():
            if task.status != TaskStatus.BLOCKED:
                continue
            if task.updated_at > stale_cutoff:
                continue
            if self._should_escalate(task.id, escalate_after_hits, stale_hit_counts):
                continue
            suggested_next_step = self._runtime_suggested_next_step(task.id)
            is_replan = self._needs_replan(task, suggested_next_step)
            followup_objective = (
                suggested_next_step
                if is_replan and suggested_next_step.startswith("Replan task:")
                else f"Replan task: {task.objective}"
                if is_replan
                else f"Resolve blocker: {task.objective}"
            )
            if followup_objective in existing_followups:
                continue
            success_criteria = (
                [
                    "A revised execution path addresses the failed verification evidence.",
                    "The next execution step is explicit and testable.",
                ]
                if is_replan
                else ["Blocker is clarified or removed."]
            )
            unmet_output_keys = self._runtime_unmet_contract_output_keys(task.id)
            unmet_outputs = self._runtime_unmet_contract_outputs(task.id)
            if is_replan and unmet_output_keys:
                success_criteria.append(f"Resolve unmet contract requirements: {', '.join(unmet_output_keys)}.")
            followup_tags = ["task:replan", f"source_task:{task.id}"] if is_replan else [f"source_task:{task.id}"]
            followup = self.task_engine.create(
                TaskCreatePayload(
                    objective=followup_objective,
                    success_criteria=success_criteria,
                    risk_level=task.risk_level,
                    tags=followup_tags,
                )
            )
            self.relation_service.link("task", task.id, "spawned_followup", "task", followup.id)
            created.append(task.id)
            self.event_repo.append(
                "scheduler.stalled_task.replan_created" if is_replan else "scheduler.stalled_task.followup_created",
                {
                    "task_id": task.id,
                    "followup_task_id": followup.id,
                    "stale_after_minutes": stale_after_minutes,
                    "reason": "verification_failed" if is_replan else "blocked",
                    "suggested_next_step": suggested_next_step,
                    "unmet_contract_output_keys": unmet_output_keys,
                    "unmet_contract_outputs": unmet_outputs,
                },
            )
        return created

    def _runtime_suggested_next_step(self, task_id: str) -> str:
        run = self.delivery.execution_runs.latest_for_task(task_id)
        if not run:
            return ""
        implementation_result = run.metadata.get("runtime_implementation_result", {})
        if not isinstance(implementation_result, dict):
            return ""
        suggested_next_step = implementation_result.get("suggested_next_step", "")
        return suggested_next_step if isinstance(suggested_next_step, str) else ""

    def _runtime_unmet_contract_outputs(self, task_id: str) -> list[str]:
        run = self.delivery.execution_runs.latest_for_task(task_id)
        if not run:
            return []
        verification_summary = run.metadata.get("verification_summary", {})
        if not isinstance(verification_summary, dict):
            return []
        unmet_outputs = verification_summary.get("unmet_contract_outputs", [])
        if not isinstance(unmet_outputs, list):
            return []
        return [str(item) for item in unmet_outputs if item]

    def _runtime_unmet_contract_output_keys(self, task_id: str) -> list[str]:
        run = self.delivery.execution_runs.latest_for_task(task_id)
        if not run:
            return []
        verification_summary = run.metadata.get("verification_summary", {})
        if not isinstance(verification_summary, dict):
            return []
        unmet_keys = verification_summary.get("unmet_contract_output_keys", [])
        if not isinstance(unmet_keys, list):
            return []
        return [str(item) for item in unmet_keys if item]

    @staticmethod
    def _needs_replan(task: TaskRecord, suggested_next_step: str = "") -> bool:
        if suggested_next_step.startswith("Replan task:"):
            return True
        return bool(task.blocker_reason and "verification did not satisfy" in task.blocker_reason.lower())

    @staticmethod
    def _planned_task_autonomy_score(task: TaskRecord) -> int:
        score = 0
        tags = set(task.tags)
        if task.implementation_contract is not None:
            score += 3
        if task.execution_plan.runtime_name or task.runtime_name:
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
        return score

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
