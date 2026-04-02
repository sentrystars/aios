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
    LearningInsight,
    LearningRecallResponse,
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

    def annotate(self, run_id: str, metadata: dict[str, object]) -> ExecutionRunRecord:
        run = self.repo.get(run_id)
        if not run:
            raise ValueError(f"Execution run {run_id} not found.")
        run.metadata = {**run.metadata, **metadata}
        saved = self.repo.update(run)
        self.events.append(
            "execution_run.updated",
            {
                "id": saved.id,
                "task_id": saved.task_id,
                "status": saved.status,
                "metadata": metadata,
            },
        )
        return saved

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


class GoalService:
    def __init__(
        self,
        repo: GoalRepository,
        events: EventRepository,
        memory_engine: MemoryEngine | None = None,
        self_kernel: SelfKernel | None = None,
    ) -> None:
        self.repo = repo
        self.events = events
        self.memory_engine = memory_engine
        self.self_kernel = self_kernel

    def create(self, payload: GoalCreatePayload) -> GoalRecord:
        goal = GoalRecord(id=str(uuid4()), **payload.model_dump())
        self.events.append("goal.created", goal.model_dump(mode="json"))
        return self.repo.create(goal)

    def list(self) -> list[GoalRecord]:
        goals = self.repo.list()
        return sorted(goals, key=lambda item: (item.priority, item.updated_at), reverse=True)

    def get(self, goal_id: str) -> GoalRecord | None:
        return self.repo.get(goal_id)

    def update(self, goal_id: str, payload: GoalUpdatePayload) -> GoalRecord:
        goal = self.repo.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found.")
        updates = payload.model_dump(exclude_unset=True)
        goal = goal.model_copy(update={**updates, "updated_at": utc_now()})
        self.events.append("goal.updated", goal.model_dump(mode="json"))
        return self.repo.update(goal)

    def active(self) -> list[GoalRecord]:
        return [goal for goal in self.list() if goal.status == GoalStatus.ACTIVE]

    def refresh_progress(self, tasks: list[TaskRecord]) -> list[GoalRecord]:
        goals = self.repo.list()
        updated: list[GoalRecord] = []
        changed: list[GoalRecord] = []
        for goal in goals:
            linked = [task for task in tasks if goal.id in task.linked_goal_ids]
            if not linked:
                updated.append(goal)
                continue
            done_count = sum(1 for task in linked if task.status == TaskStatus.DONE)
            active_count = sum(1 for task in linked if task.status in {TaskStatus.PLANNED, TaskStatus.EXECUTING, TaskStatus.VERIFYING})
            derived_progress = min(1.0, (done_count + 0.5 * active_count) / max(len(linked), 1))
            status = GoalStatus.DONE if derived_progress >= 1.0 else goal.status
            if abs(derived_progress - goal.progress) > 0.001 or status != goal.status:
                goal = goal.model_copy(update={"progress": derived_progress, "status": status, "updated_at": utc_now()})
                self.repo.update(goal)
                self.events.append("goal.progress_refreshed", goal.model_dump(mode="json"))
                changed.append(goal)
            updated.append(goal)
        return changed

    def plan_goal(self, goal_id: str, task_engine: TaskEngine) -> GoalPlanResult:
        goal = self.repo.get(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found.")

        existing = [task for task in task_engine.list() if goal.id in task.linked_goal_ids]
        existing_objectives = {task.objective for task in existing}
        templates = self._planning_templates(goal, existing)
        created: list[TaskRecord] = []
        for objective, criteria, tags in templates:
            if objective in existing_objectives:
                continue
            created.append(
                task_engine.create(
                    TaskCreatePayload(
                        objective=objective,
                        success_criteria=criteria,
                        tags=[*tags, f"goal:{goal.kind.value}"],
                        linked_goal_ids=[goal.id],
                    )
                )
            )
        self.events.append(
            "goal.planned",
            {
                "goal_id": goal.id,
                "created_task_ids": [task.id for task in created],
                "created_count": len(created),
            },
        )
        summary = "Goal backlog already existed." if not created else f"Created {len(created)} goal-linked tasks."
        return GoalPlanResult(goal_id=goal.id, created_tasks=created, summary=summary)

    def _planning_templates(
        self, goal: GoalRecord, existing: list[TaskRecord]
    ) -> list[tuple[str, list[str], list[str]]]:
        lowered = " ".join([goal.title, goal.summary, " ".join(goal.tags), " ".join(goal.success_metrics)]).lower()
        recall = self.memory_engine.recall(f"{goal.title} {goal.summary}", limit=5) if self.memory_engine else None
        recall_reasons = [item.reason for item in (recall.items if recall else [])]
        relationship_names: list[str] = []
        if self.self_kernel:
            relationship_names = [
                entry.split(":", 1)[1].strip().lower()
                for entry in self.self_kernel.get().relationship_network
                if ":" in entry and entry.split(":", 1)[1].strip()
            ]
        templates: list[tuple[str, list[str], list[str]]] = [
            (
                f"Clarify execution path for goal: {goal.title}",
                [
                    "The goal scope, constraints, and stakeholders are explicit.",
                    *([f"Relevant recalled context: {reason}" for reason in recall_reasons[:1]] if recall_reasons else []),
                ],
                ["goal:clarify"],
            )
        ]
        if any(token in lowered for token in ("schedule", "calendar", "meeting", "review", "cadence")):
            templates.append(
                (
                    f"Schedule working session for goal: {goal.title}",
                    ["A concrete calendar slot exists for this goal."],
                    ["goal:schedule", "calendar"],
                )
            )
        if any(token in lowered for token in ("write", "draft", "doc", "plan", "spec", "roadmap")):
            templates.append(
                (
                    f"Draft primary artifact for goal: {goal.title}",
                    goal.success_metrics or ["A concrete deliverable exists for this goal."],
                    ["goal:deliver", "artifact"],
                )
            )
        else:
            templates.append(
                (
                    f"Create deliverable for goal: {goal.title}",
                    goal.success_metrics or ["A concrete deliverable exists for this goal."],
                    ["goal:deliver"],
                )
            )
        if any(token in lowered for token in ("contact", "partner", "alice", "vendor", "customer", "stakeholder")):
            templates.append(
                (
                    f"Prepare stakeholder alignment for goal: {goal.title}",
                    ["Stakeholder-facing coordination is reviewed before action."],
                    ["goal:stakeholder", "coordination"],
                )
            )
        elif any(name in lowered for name in relationship_names):
            templates.append(
                (
                    f"Review relationship-sensitive path for goal: {goal.title}",
                    ["Relationship-sensitive context is reviewed before execution."],
                    ["goal:relationship_review", "coordination"],
                )
            )
        if goal.kind.value in {"initiative", "north_star"} and not existing:
            templates.append(
                (
                    f"Break down milestone map for goal: {goal.title}",
                    ["The goal is decomposed into smaller milestones or projects."],
                    ["goal:decompose"],
                )
            )
        if recall_reasons:
            templates.append(
                (
                    f"Apply recalled lessons to goal: {goal.title}",
                    ["Relevant historical memory is translated into execution guardrails."],
                    ["goal:memory_context"],
                )
            )
        templates.append(
            (
                f"Review progress for goal: {goal.title}",
                ["Progress is measured and the next iteration is clear."],
                ["goal:review"],
            )
        )
        return templates


class DeviceService:
    def __init__(self, repo: DeviceRepository, events: EventRepository) -> None:
        self.repo = repo
        self.events = events

    def upsert(self, payload: DeviceUpsertPayload) -> DeviceRecord:
        existing = self.repo.get(payload.id)
        device = DeviceRecord(
            **payload.model_dump(),
            last_seen_at=utc_now(),
        )
        self.events.append("device.registered" if existing is None else "device.updated", device.model_dump(mode="json"))
        return self.repo.upsert(device)

    def list(self) -> list[DeviceRecord]:
        return self.repo.list()


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

    def recall(self, query: str, limit: int = 5) -> MemoryRecallResponse:
        lowered = query.lower()
        scored: list[tuple[float, MemoryRecord, str]] = []
        for record in self.repo.list():
            haystack = " ".join([record.title, record.content, " ".join(record.tags)]).lower()
            overlap = sum(1 for token in lowered.split() if token and token in haystack)
            if overlap == 0:
                continue
            score = min(1.0, 0.25 * overlap + 0.25 * record.confidence)
            reason = f"Matched {overlap} query terms in {record.layer.value} memory."
            scored.append((score, record, reason))
        scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return MemoryRecallResponse(
            query=query,
            items=[
                MemoryRecallItem(
                    memory_id=record.id,
                    title=record.title,
                    layer=record.layer,
                    score=score,
                    reason=reason,
                )
                for score, record, reason in scored[:limit]
            ],
        )

    def recall_learning(self, query: str, limit: int = 5) -> LearningRecallResponse:
        lowered = query.lower()
        scored: list[tuple[float, MemoryRecord, str, str]] = []
        for record in self.repo.list():
            if record.memory_type != MemoryType.LEARNING:
                continue
            haystack = " ".join([record.title, record.content, " ".join(record.tags)]).lower()
            overlap = sum(1 for token in lowered.split() if token and token in haystack)
            if query and overlap == 0:
                continue
            category = self._learning_category(record)
            category_bonus = 0.15 if category in lowered else 0.0
            score = min(1.0, 0.2 * overlap + 0.4 * record.confidence + category_bonus)
            reason = (
                f"Matched {overlap} query terms in structured {category} learning."
                if query
                else f"Recent structured {category} learning."
            )
            scored.append((score, record, reason, category))
        scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return LearningRecallResponse(
            query=query,
            items=[
                LearningInsight(
                    memory_id=record.id,
                    title=record.title,
                    category=category,
                    score=score,
                    reason=reason,
                    confidence=record.confidence,
                    tags=record.tags,
                )
                for score, record, reason, category in scored[:limit]
            ],
        )

    def reflect_task(self, task: TaskRecord, payload: TaskReflectionPayload) -> MemoryRecord:
        content = payload.summary
        if payload.lessons:
            content = f"{content}\nLessons:\n- " + "\n- ".join(payload.lessons)
        record = MemoryRecord(
            id=str(uuid4()),
            memory_type=MemoryType.REFLECTION,
            layer=MemoryLayer.PROCEDURAL,
            title=f"Reflection for task {task.id}",
            content=content,
            tags=["task_reflection", task.id],
            source="ai_os_reflection",
            confidence=0.9,
            freshness="active",
            related_goal_ids=task.linked_goal_ids,
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
        for learning in self._derive_learning_records(task, payload):
            derived = self.repo.create(learning)
            self.events.append("memory.learning_created", derived.model_dump(mode="json"))
            self.relations.link(
                source_type="task",
                source_id=task.id,
                relation_type="produced_learning",
                target_type="memory",
                target_id=derived.id,
            )
        return saved

    @staticmethod
    def _learning_category(record: MemoryRecord) -> str:
        for tag in record.tags:
            if tag.startswith("learning:"):
                return tag.split(":", 1)[1]
        return "general"

    @staticmethod
    def _tokenize_text(value: str) -> list[str]:
        tokens: list[str] = []
        current: list[str] = []
        for char in value.lower():
            if char.isalnum():
                current.append(char)
                continue
            if current:
                token = "".join(current)
                if len(token) >= 3:
                    tokens.append(token)
                current = []
        if current:
            token = "".join(current)
            if len(token) >= 3:
                tokens.append(token)
        return tokens

    def _derive_learning_records(self, task: TaskRecord, payload: TaskReflectionPayload) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        runtime_name = task.runtime_name or task.execution_plan.runtime_name or "none"
        status_value = task.status.value
        base_tags = [
            "learning:reflection",
            f"task:{task.id}",
            f"status:{status_value}",
            f"execution_mode:{task.execution_mode.value}",
            f"runtime:{runtime_name}",
        ]
        for token in self._tokenize_text(task.objective)[:6]:
            base_tags.append(f"objective:{token}")
        records.append(
            MemoryRecord(
                id=str(uuid4()),
                memory_type=MemoryType.LEARNING,
                layer=MemoryLayer.PROCEDURAL,
                title=f"Task outcome learning: {task.objective[:80]}",
                content=(
                    f"Objective: {task.objective}\n"
                    f"Outcome: {payload.summary}\n"
                    f"Runtime: {runtime_name}\n"
                    f"Execution mode: {task.execution_mode.value}\n"
                    f"Status at reflection: {status_value}"
                ),
                tags=base_tags,
                source="ai_os_learning",
                confidence=0.8,
                freshness="active",
                related_goal_ids=task.linked_goal_ids,
            )
        )
        for lesson in payload.lessons:
            category, normalized_tags, title = self._classify_lesson(lesson, task, runtime_name)
            records.append(
                MemoryRecord(
                    id=str(uuid4()),
                    memory_type=MemoryType.LEARNING,
                    layer=MemoryLayer.PROCEDURAL,
                    title=title,
                    content=lesson,
                    tags=normalized_tags,
                    source="ai_os_learning",
                    confidence=0.9,
                    freshness="active",
                    related_goal_ids=task.linked_goal_ids,
                )
            )
        return records

    def _classify_lesson(self, lesson: str, task: TaskRecord, runtime_name: str) -> tuple[str, list[str], str]:
        lowered = lesson.lower().strip()
        parts = [part.strip() for part in lowered.split(":") if part.strip()]
        category = parts[0] if parts else "strategy"
        normalized_tags = [
            f"learning:{category}",
            f"task:{task.id}",
            f"execution_mode:{task.execution_mode.value}",
            f"runtime:{runtime_name}",
        ]
        for part in parts[1:]:
            normalized_tags.append(f"context:{part}")
        for token in self._tokenize_text(lesson)[:6]:
            normalized_tags.append(f"lesson:{token}")
        detail = " / ".join(parts[1:3]) if len(parts) > 1 else task.objective[:48]
        title = f"{category.title()} lesson: {detail}"
        return category, normalized_tags, title
